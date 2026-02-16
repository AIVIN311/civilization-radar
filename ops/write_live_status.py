import hashlib
import json
import os
from datetime import datetime, timezone


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IN_PATH = os.path.join(REPO, "input", "snapshots.jsonl")
OUT_DIR = os.path.join(REPO, "output", "live")
OUT_JSON = os.path.join(OUT_DIR, "live_snapshot_status.json")
OUT_DOMAINS = os.path.join(OUT_DIR, "latest_day_domains.txt")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_date_bucket(row: dict) -> str | None:
    """
    Resolve row date bucket.
    Priority:
      1) ts -> UTC date
      2) date field
    """
    ts = row.get("ts")
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date().isoformat()
        except Exception:
            pass

    d = row.get("date")
    if d:
        try:
            return str(d)[:10]
        except Exception:
            pass
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.exists(IN_PATH):
        raise SystemExit(f"missing: {IN_PATH}")

    total_rows = 0
    empty_lines = 0
    bad_json_lines = 0
    bucket_dates: list[str] = []

    with open(IN_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                empty_lines += 1
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad_json_lines += 1
                continue

            total_rows += 1
            bucket = resolve_date_bucket(obj)
            if bucket:
                bucket_dates.append(bucket)

    if not bucket_dates:
        raise SystemExit("no valid date bucket found in snapshots.jsonl")

    min_date = min(bucket_dates)
    max_date = max(bucket_dates)

    today_pairs: set[tuple[str, str]] = set()
    today_domains: set[str] = set()

    with open(IN_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            bucket = resolve_date_bucket(obj)
            if bucket != max_date:
                continue

            domain = obj.get("domain")
            if not isinstance(domain, str) or not domain:
                continue

            domain_l = domain.lower()
            today_pairs.add((bucket, domain_l))
            today_domains.add(domain_l)

    mtime_iso = datetime.fromtimestamp(os.path.getmtime(IN_PATH), tz=timezone.utc).isoformat()
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "input_path": IN_PATH,
        "file_mtime_utc": mtime_iso,
        "min_date": min_date,
        "max_date": max_date,
        "total_rows": total_rows,
        "empty_lines": empty_lines,
        "bad_json_lines": bad_json_lines,
        "today_rows_unique_date_domain": len(today_pairs),
        "today_unique_domains": len(today_domains),
        # Reserved for future expansion. Kept null intentionally in v0.7
        # to avoid introducing false-positive duplicate estimates.
        "dups_date_domain_estimate": None,
        "input_sha256": sha256_file(IN_PATH),
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(OUT_DOMAINS, "w", encoding="utf-8") as f:
        for domain in sorted(today_domains):
            f.write(domain + "\n")

    print(f"[live status] wrote: {OUT_JSON}", flush=True)
    print(f"[live status] wrote: {OUT_DOMAINS}", flush=True)
    print(
        "[live status] "
        f"max_date={max_date} "
        f"today_unique_domains={len(today_domains)} "
        f"total_rows={total_rows} "
        f"bad_json_lines={bad_json_lines} "
        f"empty_lines={empty_lines}",
        flush=True,
    )


if __name__ == "__main__":
    main()
