# cf_pull_daily_v2.py
# Pull Cloudflare daily traffic via GraphQL, append to JSONL, dedupe by (date, domain)
# Supports: --days, --out, --allowlist
# Output row fields: date, domain, dns_total, cf_served, origin_served, edge_origin_ratio

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone

import requests

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


API_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
API_ZONES = "https://api.cloudflare.com/client/v4/zones"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


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
    r = requests.post(API_GRAPHQL, headers=headers, json={"query": query, "variables": variables}, timeout=60)
    r.raise_for_status()
    j = r.json()
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
        r = requests.get(API_ZONES, headers=headers, params={"page": page, "per_page": per_page}, timeout=60)
        r.raise_for_status()
        j = r.json()
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

    ensure_parent_dir(args.out)
    existing = read_existing_keys(args.out)

    zones = get_zones(headers)
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

            if allow is not None and dom_l not in allow:
                continue

            data = fetch_daily(headers, zid, since)

            zones_arr = (((data.get("viewer") or {}).get("zones")) or [])
            if not zones_arr:
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

    print(f"✅ daily_snapshots.jsonl generated: {args.out}")
    print(f"✅ rows written: {rows_written}")
    print(f"✅ zones scanned: {zones_scanned}")
    print(f"✅ since: {since} (UTC)")


if __name__ == "__main__":
    main()
