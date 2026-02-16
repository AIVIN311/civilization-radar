# cf_pull_daily_v2.py
# Pull Cloudflare daily traffic via GraphQL, append to JSONL, dedupe by (date, domain)
# Supports: --days, --out, --allowlist
# Output row fields: date, domain, dns_total, cf_served, origin_served, edge_origin_ratio

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


API_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
API_ZONES = "https://api.cloudflare.com/client/v4/zones"
MAX_ATTEMPTS = 5
BASE_SLEEP_SEC = 2.0
JITTER_MAX_SEC = 0.5
SLEEP_CAP_SEC = 30.0
HTTP_TIMEOUT = (10, 60)


def eprint(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, file=sys.stderr, **kwargs)


def _retry_sleep(attempt: int) -> float:
    backoff = BASE_SLEEP_SEC * (2 ** (attempt - 1))
    return min(SLEEP_CAP_SEC, backoff) + random.uniform(0.0, JITTER_MAX_SEC)


def request_with_retry(
    method: str,
    url: str,
    headers: dict,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    endpoint: str,
):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=HTTP_TIMEOUT,
            )

            status = int(r.status_code)
            if status == 429:
                raise SystemExit(
                    f"{endpoint} non-retryable HTTP 429 rate-limit "
                    f"(attempt={attempt}/{MAX_ATTEMPTS})."
                )
            if 500 <= status <= 599:
                if attempt < MAX_ATTEMPTS:
                    sleep_sec = _retry_sleep(attempt)
                    print(
                        f"WARN retry endpoint={endpoint} attempt={attempt}/{MAX_ATTEMPTS} "
                        f"reason=HTTP_{status} sleep={sleep_sec:.2f}s",
                        flush=True,
                    )
                    time.sleep(sleep_sec)
                    continue
                raise SystemExit(
                    f"{endpoint} failed after {attempt}/{MAX_ATTEMPTS} attempts "
                    f"(last_status=HTTP_{status})."
                )

            r.raise_for_status()
            return r
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < MAX_ATTEMPTS:
                sleep_sec = _retry_sleep(attempt)
                print(
                    f"WARN retry endpoint={endpoint} attempt={attempt}/{MAX_ATTEMPTS} "
                    f"reason={type(e).__name__} sleep={sleep_sec:.2f}s",
                    flush=True,
                )
                time.sleep(sleep_sec)
                continue
            raise SystemExit(
                f"{endpoint} failed after {attempt}/{MAX_ATTEMPTS} attempts "
                f"(last_error={type(e).__name__}: {e})."
            ) from e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            raise SystemExit(
                f"{endpoint} non-retryable HTTP error status={status} detail={e}"
            ) from e
        except requests.RequestException as e:
            raise SystemExit(
                f"{endpoint} non-retryable request error {type(e).__name__}: {e}"
            ) from e

    raise SystemExit(f"{endpoint} failed without response after {MAX_ATTEMPTS} attempts.")


def load_allowlist(path: str | None) -> set[str] | None:
    if not path:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(f"allowlist not found: {path}")
    allowed = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            allowed.add(s.lower())
    return allowed


def ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def read_existing_keys(jsonl_path: str) -> set[tuple[str, str]]:
    """Return set of (date, domain) already in output to dedupe."""
    keys: set[tuple[str, str]] = set()
    if not os.path.exists(jsonl_path):
        return keys
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                d = obj.get("date")
                dom = obj.get("domain")
                if isinstance(d, str) and isinstance(dom, str):
                    keys.add((d, dom.lower()))
            except Exception:
                # ignore bad lines (keep robust)
                continue
    return keys


def graphql(headers: dict, query: str, variables: dict):
    r = request_with_retry(
        method="POST",
        url=API_GRAPHQL,
        headers=headers,
        json_body={"query": query, "variables": variables},
        endpoint="Cloudflare GraphQL",
    )
    try:
        j = r.json()
    except ValueError as e:
        raise SystemExit(f"Cloudflare GraphQL returned invalid JSON: {e}") from e
    if j.get("errors"):
        eprint("❌ Cloudflare GraphQL errors:")
        eprint(json.dumps(j["errors"], ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL query failed (see errors above).")
    if j.get("data") is None:
        eprint("❌ GraphQL returned data=None. Raw response:")
        eprint(json.dumps(j, ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL returned no data.")
    return j["data"]


def get_zones(headers: dict) -> list[dict]:
    zones = []
    page = 1
    per_page = 50

    while True:
        r = request_with_retry(
            method="GET",
            url=API_ZONES,
            headers=headers,
            params={"page": page, "per_page": per_page},
            endpoint="Cloudflare Zones API",
        )
        try:
            j = r.json()
        except ValueError as e:
            raise SystemExit(f"Zones API returned invalid JSON: {e}") from e
        if not j.get("success"):
            raise SystemExit(f"Zones API failed: {json.dumps(j, ensure_ascii=False)}")
        result = j.get("result", [])
        zones.extend(result)
        info = j.get("result_info") or {}
        total_pages = info.get("total_pages", page)
        if page >= total_pages:
            break
        page += 1

    return zones


def fetch_daily(headers: dict, zone_tag: str, since_date_utc: str):
    # NOTE:
    # - Do NOT query zone fields like id/name in GraphQL (often restricted/changed).
    # - Use REST /zones to list zones (id + name) and then zoneTag here.
    query = """
    query($zone: String!, $since: Date!) {
      viewer {
        zones(filter: { zoneTag: $zone }) {
          httpRequests1dGroups(limit: 60, filter: { date_geq: $since }) {
            dimensions { date }
            sum {
              requests
              cachedRequests
            }
          }
        }
      }
    }
    """
    return graphql(headers, query, {"zone": zone_tag, "since": since_date_utc})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="how many days back (UTC) to pull")
    ap.add_argument("--out", type=str, default="output/daily_snapshots.jsonl", help="output jsonl path")
    ap.add_argument("--allowlist", type=str, default=None, help="text file of domains to include (one per line)")
    args = ap.parse_args()

    if load_dotenv:
        load_dotenv()

    token = os.getenv("CF_API_TOKEN")
    if not token:
        raise SystemExit("Missing CF_API_TOKEN in environment. Put it in .env then reopen terminal, or set env var.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    allow = load_allowlist(args.allowlist)
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    started = time.time()

    ensure_parent_dir(args.out)
    existing = read_existing_keys(args.out)
    print(
        f"START daily collect out={args.out} days={args.days} since={since} (UTC)",
        flush=True,
    )

    zones = get_zones(headers)
    zones_total = len(zones)
    print(f"START zones_total={zones_total}", flush=True)
    zones_scanned = 0
    rows_written = 0

    # append mode
    with open(args.out, "a", encoding="utf-8") as f:
        for z in zones:
            name = (z.get("name") or "").strip()
            zid = (z.get("id") or "").strip()
            if not name or not zid:
                continue

            zones_scanned += 1
            dom_l = name.lower()
            should_report = zones_scanned % 10 == 0 or zones_scanned == zones_total

            if allow is not None and dom_l not in allow:
                if should_report:
                    print(
                        f"progress scanned={zones_scanned}/{zones_total} "
                        f"rows_written={rows_written} zone={name}",
                        flush=True,
                    )
                continue

            data = fetch_daily(headers, zid, since)

            zones_arr = (((data.get("viewer") or {}).get("zones")) or [])
            if not zones_arr:
                if should_report:
                    print(
                        f"progress scanned={zones_scanned}/{zones_total} "
                        f"rows_written={rows_written} zone={name}",
                        flush=True,
                    )
                continue

            groups = zones_arr[0].get("httpRequests1dGroups") or []
            for g in groups:
                date = (g.get("dimensions") or {}).get("date")
                s = g.get("sum") or {}
                requests_total = int(s.get("requests") or 0)
                cached_requests = int(s.get("cachedRequests") or 0)

                if not isinstance(date, str) or not date:
                    continue

                key = (date, dom_l)
                if key in existing:
                    continue

                origin_served = max(0, requests_total - cached_requests)

                row = {
                    "date": date,
                    "domain": name,
                    "dns_total": requests_total,
                    "cf_served": cached_requests,
                    "origin_served": origin_served,
                    "edge_origin_ratio": round(cached_requests / origin_served, 4) if origin_served > 0 else 0.0,
                }

                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                existing.add(key)
                rows_written += 1

            if should_report:
                print(
                    f"progress scanned={zones_scanned}/{zones_total} "
                    f"rows_written={rows_written} zone={name}",
                    flush=True,
                )

    elapsed = time.time() - started
    print(f"✅ daily_snapshots.jsonl generated: {args.out}", flush=True)
    print(f"✅ rows written: {rows_written}", flush=True)
    print(f"✅ zones scanned: {zones_scanned}", flush=True)
    print(f"✅ since: {since} (UTC)", flush=True)
    print(
        f"DONE zones_scanned={zones_scanned} rows_written={rows_written} "
        f"since={since} elapsed={elapsed:.2f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
