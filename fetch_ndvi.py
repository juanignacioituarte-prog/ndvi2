import os
import json
import csv
import requests
from datetime import datetime, timedelta

# Sentinel Hub credentials from environment variables
CLIENT_ID = os.environ["SH_CLIENT_ID"]
CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]

# GCS paddocks JSON URL
PADDOCKS_URL = "https://storage.googleapis.com/ndvi-exports/paddocks_ndvi.json"

# Output files
OUTPUT_JSON = "paddocks_ndvi.json"
OUTPUT_CSV = "paddocks_ndvi.csv"

# Sentinel Hub OAuth token URL
TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"

# Sentinel Hub WCS / Process API endpoint (example, adjust if needed)
PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"

def get_token():
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(TOKEN_URL, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def fetch_paddocks():
    r = requests.get(PADDOCKS_URL)
    r.raise_for_status()
    return r.json()

def fetch_ndvi_for_paddock(paddock_name):
    # Dummy geometry placeholder — replace with real paddock geometry if available
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0,0],[0,1],[1,1],[1,0],[0,0]]]
    }
    
    # Sentinel Hub request body
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    body = {
        "input": {
            "bounds": {"geometry": geometry},
            "data": [{"type": "S2L2A"}]
        },
        "output": {"responses": [{"identifier": "default", "format": {"type": "json"}}]},
        "dataFilter": {
            "timeRange": {"from": yesterday.strftime("%Y-%m-%dT00:00:00Z"), 
                          "to": now.strftime("%Y-%m-%dT23:59:59Z")}
        }
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(PROCESS_URL, headers=headers, json=body)
    if r.status_code != 200:
        print(f"Warning: failed NDVI fetch for {paddock_name}: {r.status_code}")
        return None

    data = r.json()
    # Simplified: assume NDVI value in data['data'][0]['ndvi'] or similar
    ndvi_value = data.get("data", [{}])[0].get("ndvi", None)
    return ndvi_value

def main():
    global TOKEN
    TOKEN = get_token()
    paddocks = fetch_paddocks()

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    for paddock in paddocks:
        name = paddock.get("paddock_name")
        if not name:
            continue
        ndvi = fetch_ndvi_for_paddock(name)
        results.append({
            "paddock_name": name,
            "ndvi": ndvi,
            "date_utc": now_str
        })

    # Save JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)

    # Save CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["paddock_name","ndvi","date_utc"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} paddocks NDVI to {OUTPUT_JSON} and {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
