import os
import requests
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("CF_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

API = "https://api.cloudflare.com/client/v4/graphql"

def graphql(query, variables={}):
    r = requests.post(API, headers=HEADERS, json={
        "query": query,
        "variables": variables
    })
    r.raise_for_status()
    j = r.json()

    # ✅ 這行是關鍵：Cloudflare 有 errors 時，data 會是 null
    if j.get("errors"):
        print("❌ Cloudflare GraphQL errors:")
        print(json.dumps(j["errors"], ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL query failed (see errors above).")

    if j.get("data") is None:
        print("❌ GraphQL returned data=None, raw response:")
        print(json.dumps(j, ensure_ascii=False, indent=2))
        raise SystemExit("GraphQL returned no data.")

    return j["data"]

def get_zones():
    query = """
    query {
      viewer {
        zones {
          zoneTag
          name
        }
      }
    }
    """
    result = graphql(query)  # 這裡回的是 data
    return result["viewer"]["zones"]

def fetch_daily(zone_id, since):
    query = """
    query($zone: String!, $since: Date!) {
  viewer {
    zones(filter: {zoneTag: $zone}) {
      httpRequests1dGroups(limit: 30, filter: {date_geq: $since}) {
        dimensions { date }
        sum { requests cachedRequests uncachedRequests }
      }
    }
  }
}
    """
    return graphql(query, {
        "zone": zone_id,
        "since": since
    })

def main(days=7, out="daily_snapshots.jsonl"):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    zones = get_zones()

    with open(out, "w", encoding="utf-8") as f:
        for z in zones:
            name = z["name"]
            zid = z["zoneTag"]

            data = fetch_daily(zid, since)

            groups = data["viewer"]["zones"][0]["httpRequests1dGroups"]

            for g in groups:
                row = {
                    "date": g["dimensions"]["date"],
                    "domain": name,
                    "dns_total": g["sum"]["requests"],
                    "cf_served": g["sum"]["cachedRequests"],
                    "origin_served": g["sum"]["uncachedRequests"],
                }

                if row["origin_served"] > 0:
                    row["edge_origin_ratio"] = round(
                        row["cf_served"] / row["origin_served"], 4
                    )
                else:
                    row["edge_origin_ratio"] = None

                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("✅ daily_snapshots.jsonl generated")

if __name__ == "__main__":
    main()
