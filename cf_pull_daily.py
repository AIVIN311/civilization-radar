import os
import requests
import json
from datetime import datetime, timedelta
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
    return r.json()

def get_zones():
    url = "https://api.cloudflare.com/client/v4/zones"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()["result"]

def fetch_daily(zone_id, since):
    query = """
    query($zone: String!, $since: DateTime!) {
      viewer {
        zones(filter: {zoneTag: $zone}) {
          httpRequests1dGroups(limit: 30, filter: {date_geq: $since}) {
            dimensions { date }
            sum {
              requests
              cachedRequests
              uncachedRequests
            }
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
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    zones = get_zones()

    with open(out, "w", encoding="utf-8") as f:
        for z in zones:
            name = z["name"]
            zid = z["id"]

            data = fetch_daily(zid, since)

            groups = data["data"]["viewer"]["zones"][0]["httpRequests1dGroups"]

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
