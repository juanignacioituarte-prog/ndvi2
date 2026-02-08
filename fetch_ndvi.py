import os
import json
import csv
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. SETTINGS
CLIENT_ID = os.environ.get("SH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")
PADDOCKS_URL = "https://storage.googleapis.com/ndvi-exports/paddocks.geojson"
OUTPUT_CSV = "paddocks_ndvi.csv"

# 2. AUTHENTICATION
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

# 3. FETCH PADDOCKS
def fetch_paddock_geometries():
    r = requests.get(PADDOCKS_URL)
    r.raise_for_status()
    return r.json()["features"]

# 4. FETCH NDVI DATA WITH < 40% CLOUD CHECK
def get_paddock_ndvi(token, geometry):
    url = "https://services.sentinel-hub.com/api/v1/statistics"
    now = datetime.utcnow()
    # Looking back 30 days to find a clear image
    start = now - timedelta(days=30)
    
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
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
      // SCL bands 3, 8, 9, 10 are clouds or shadows
      let isCloud = [3, 8, 9, 10].includes(samples.SCL);
      return { 
        stats: [ndvi], 
        dataMask: [isCloud ? 0 : 1] 
      };
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
        return None, None

    stats_data = r.json().get("data", [])
    
    # Check images starting from the most recent
    for entry in reversed(stats_data):
        outputs = entry.get("outputs", {})
        
        # Calculate cloud percentage based on dataMask
        mask_stats = outputs.get("dataMask", {}).get("bands", [{}])[0].get("stats", {})
        sample_count = mask_stats.get("sampleCount", 0)
        no_data_count = mask_stats.get("noDataCount", 0)
        
        if sample_count > 0:
            cloud_pc = (no_data_count / sample_count) * 100
            
            # Enforce 40% cloud threshold
            if cloud_pc < 40:
                bands = outputs.get("stats", {}).get("bands", [])
                if bands and len(bands) > 0:
                    val = bands[0].get("stats", {}).get("mean")
                    date_found = entry.get("interval", {}).get("from", "")[:10]
                    if val is not None:
                        return round(val, 3), date_found
                        
    return None, None

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: SH_CLIENT_ID or SH_CLIENT_SECRET not set.")
        return

    token = get_token()
    features = fetch_paddock_geometries()
    results = []
    
    print(f"Processing {len(features)} paddocks...")
    
    for feat in features:
        # Check for 'name' or 'paddock_name' in geojson properties
        props = feat.get("properties", {})
        name = props.get("name") or props.get("paddock_name") or "Unknown"
        geometry = feat["geometry"]
        
        print(f"Fetching NDVI for {name}...")
        ndvi_val, date_obs = get_paddock_ndvi(token, geometry)
        
        results.append({
            "paddock_name": name,
            "ndvi": ndvi_val,
            "observation_date": date_obs,
            "processed_at": datetime.utcnow().strftime("%Y-%m-%d")
        })

    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done! Saved {len(results)} rows to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
