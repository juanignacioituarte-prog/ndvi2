import os
import json
import csv
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. SETTINGS
CLIENT_ID = os.environ["SH_CLIENT_ID"]
CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
PADDOCKS_URL = "https://storage.googleapis.com/ndvi-exports/paddocks.geojson"
OUTPUT_CSV = "paddocks_ndvi.csv"

# 2. AUTHENTICATION
def get_token():
    url = "https://services.sentinel-hub.com/oauth/token"
    data = {"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# 3. FETCH PADDOCKS
def fetch_paddock_geometries():
    r = requests.get(PADDOCKS_URL)
    r.raise_for_status()
    return r.json()["features"]

# 4. FETCH NDVI DATA
def get_paddock_ndvi(token, geometry):
    url = "https://services.sentinel-hub.com/api/v1/statistics"
    
    # Requesting NDVI statistics for the last 15 days
    now = datetime.utcnow()
    start = now - timedelta(days=15)
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Evalscript to calculate NDVI
    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: [{bands: ["B04", "B08", "SCL"]}],
        output: [
          {id: "stats", bands: 1},
          {id: "dataMask", bands: 1}
        ]
      };
    }
    function evaluatePixel(samples) {
      let ndvi = (samples.B08 - samples.B04) / (samples.B08 + samples.B04);
      // Mask out clouds (SCL 3, 8, 9, 10)
      let mask = 1;
      if ([3, 8, 9, 10].includes(samples.SCL)) { mask = 0; }
      return { stats: [ndvi], dataMask: [mask] };
    }
    """

    body = {
        "input": {
            "bounds": {"geometry": geometry},
            "data": [{"type": "sentinel-2-l2a"}]
        },
        "aggregation": {
            "timeRange": {
                "from": start.strftime("%Y-%m-%dT00:00:00Z"),
                "to": now.strftime("%Y-%m-%dT23:59:59Z")
            },
            "aggregationInterval": {"of": "P1D"},
            "evalscript": evalscript,
            "resampling": "BILINEAR"
        }
    }

    r = requests.post(url, headers=headers, json=body)
    if r.status_code != 200:
        return None

    # Get the most recent valid (non-cloudy) result
    stats = r.json().get("data", [])
    for entry in reversed(stats): # Work backwards from today
        val = entry.get("outputs", {}).get("stats", {}).get("bands", [{}])[0].get("stats", {}).get("mean")
        if val is not None:
            return round(val, 3)
    return None

def main():
    token = get_token()
    features = fetch_paddock_geometries()
    results = []
    
    print(f"Processing {len(features)} paddocks...")
    
    for feat in features:
        name = feat["properties"].get("name") or feat["properties"].get("paddock_name")
        geometry = feat["geometry"]
        
        print(f"Fetching NDVI for {name}...")
        ndvi_val = get_paddock_ndvi(token, geometry)
        
        results.append({
            "paddock_name": name,
            "ndvi": ndvi_val,
            "date_utc": datetime.utcnow().strftime("%Y-%m-%d")
        })

    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done! Saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
