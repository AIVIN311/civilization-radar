import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# ---------- Config ----------
load_dotenv()
TOKEN = os.getenv("CF_API_TOKEN")

if not TOKEN:
    raise SystemExit("❌ CF_API_TOKEN not found. Put it in .env as CF_API_TOKEN=xxxxx")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

API_GQL = "https://api.cloudflare.com/client/v4/graphql"
API_ZONES = "https://api.cloudflare.com/client/v4/zones"


# ---------- Helpers ----------
def graphql(query: str, variables: dict | None = None) -> dict:
    variables = variables or {}
    r = requests.post(
        API_GQL,
        headers=HEADERS,
        json={"query": query, "variables": variables},
        timeout=60
    )
    r.raise_for_status()
    j = r.json()

    # Cloudflare GraphQL: if errors exist, data can be null
    if j.get("errors"):
        print("❌ Cloudflare GraphQL errors:")
        print(json.dumps(j["errors"], ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL query failed (see errors above).")

    if j.get("data") is None:
        print("❌ GraphQL returned data=None, raw response:")
        print(json.dumps(j, ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL returned no data.")

    return j["data"]


def get_zones(per_page: int = 200) -> list[dict]:
    # REST is the most stable way to list zones (works regardless of GraphQL schema differences)
    url = f"{API_ZONES}?per_page={per_page}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    j = r.json()

    if not j.get("success"):
        print("❌ REST /zones failed:")
        print(json.dumps(j, ensure_ascii=False, indent=2))
        raise SystemExit("REST zones failed.")

    return j["result"]  # list of {id,name,...}


def fetch_daily_http(zone_id: str, since_date: str) -> list[dict]:
    """
    Return list of daily groups:
      [{ "date": "YYYY-MM-DD", "requests": int, "cachedRequests": int }, ...]
    """
    query = """
    query($zone: String!, $since: Date!) {
      viewer {
        zones(filter: {zoneTag: $zone}) {
          httpRequests1dGroups(limit: 30, filter: {date_geq: $since}) {
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
    data = graphql(query, {"zone": zone_id, "since": since_date})

    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return []

    groups = zones[0].get("httpRequests1dGroups", [])
    out = []
    for g in groups:
        out.append({
            "date": g["dimensions"]["date"],
            "requests": g["sum"].get("requests", 0) or 0,
            "cachedRequests": g["sum"].get("cachedRequests", 0) or 0
        })
    return out


# ---------- Main ----------
def main(days: int = 7, out: str = "daily_snapshots.jsonl"):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    zones = get_zones()
    if not zones:
        raise SystemExit("❌ No zones returned. Check token permissions / resources scope.")

    written = 0

    with open(out, "w", encoding="utf-8") as f:
        for z in zones:
            name = z.get("name")
            zid = z.get("id")
            if not name or not zid:
                continue

            groups = fetch_daily_http(zid, since)

            # some zones may have no analytics data (new / empty / filtered)
            for g in groups:
                req = g["requests"]
                cf = g["cachedRequests"]
                origin = req - cf
                if origin < 0:
                    origin = 0  # safety

                row = {
                    "date": g["date"],
                    "domain": name,
                    "dns_total": req,          # 你後面壓力場仍沿用這個 key
                    "cf_served": cf,
                    "origin_served": origin,
                    "edge_origin_ratio": (round(cf / origin, 4) if origin > 0 else None),
                }

                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1

    print(f"✅ daily_snapshots.jsonl generated: {out}")
    print(f"✅ rows written: {written}")
    print(f"✅ zones scanned: {len(zones)}")
    print(f"✅ since: {since} (UTC)")


if __name__ == "__main__":
    main()

