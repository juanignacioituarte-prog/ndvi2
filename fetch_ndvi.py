import os
import json
import requests
from shapely.geometry import shape, mapping
from datetime import datetime
import csv

# -------------------------
# Sentinel Hub credentials
# -------------------------
CLIENT_ID = os.environ["SH_CLIENT_ID"]
CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]

# -------------------------
# Config / files
# -------------------------
PADDOCKS_JSON_URL = "https://storage.googleapis.com/ndvi-exports/paddocks_ndvi.json"
GCS_BUCKET_CSV = "ndvi-exports"
CSV_FILE_NAME = "paddocks_ndvi.csv"

# -------------------------
# Helper: get access token
# -------------------------
def get_token():
    url = "https://services.sentinel-hub.com/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# -------------------------
# Fetch paddocks geometry
# -------------------------
def fetch_paddocks():
    r = requests.get(PADDOCKS_JSON_URL)
    r.raise_for_status()
    return r.json()

# -------------------------
# Fetch NDVI for one paddock
# -------------------------
def fetch_ndvi_for_paddock(paddock, token):
    geometry = paddock.get("geometry")
    if not geometry:
        return None

    url = "https://services.sentinel-hub.com/api/v1/statistics"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "input": {
            "bounds": {
                "geometry": geometry
            },
            "data": [
                {
                    "type": "S2L2A",
                    "dataFilter": {
                        "timeRange": {
                            "from": (datetime.utcnow().date().isoformat() + "T00:00:00Z"),
                            "to": (datetime.utcnow().date().isoformat() + "T23:59:59Z")
                        },
                        "maxCloudCoverage": 50
                    }
                }
            ]
        },
        "aggregation": {
            "evalscript": """
            //VERSION=3
            function setup() {
                return {
                    input: ["B04","B08"],
                    output: { bands: 1, sampleType: "FLOAT32" }
                };
            }
            function evaluatePixel(sample) {
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                return [ndvi];
            }
            """
        }
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    ndvi_mean = data.get("statistics", {}).get("B08_B04", {}).get("mean")
    return ndvi_mean

# -------------------------
# Main workflow
# -------------------------
def main():
    token = get_token()
    paddocks = fetch_paddocks()
    results = []

    for p in paddocks:
        ndvi_val = fetch_ndvi_for_paddock(p, token)
        results.append({
            "paddock_name": p.get("paddock_name"),
            "ndvi": ndvi_val,
            "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })

    # Save CSV locally
    with open(CSV_FILE_NAME, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["paddock_name","ndvi","date_utc"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"✅ NDVI CSV saved: {CSV_FILE_NAME}")

if __name__ == "__main__":
    main()
