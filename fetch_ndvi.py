#!/usr/bin/env python3
import os
import json
import csv
import time
import requests

# Sentinel Hub credentials
CLIENT_ID = os.environ["SH_CLIENT_ID"]
CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]

# Sentinel Hub configuration ID
CONFIG_ID = os.environ["SH_CONFIG_ID"]

# Paddocks JSON URL (must be public)
PADDOCKS_URL = "https://storage.googleapis.com/ndvi-exports/paddocks_ndvi.json"
CSV_OUTPUT = "paddocks_ndvi.csv"

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

def fetch_paddocks():
    r = requests.get(PADDOCKS_URL)
    r.raise_for_status()
    return r.json()

def fetch_ndvi_for_paddock(paddock, token):
    url = f"https://services.sentinel-hub.com/api/v1/statistics/{CONFIG_ID}"
    body = {
        "input": {
            "bounds": {"geometry": paddock["geometry"]},
            "data": [{"type": "S2L2A"}]
        },
        "aggregation": {"timeRange": {"from": "2026-01-01T00:00:00Z", "to": "2026-02-06T23:59:59Z"}},
        "output": {"type": "json"}
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(url, json=body, headers=headers)
    r.raise_for_status()
    stats = r.json()
    # Compute mean NDVI or set None
    paddock["ndvi"] = stats.get("mean", None)
    paddock["date_utc"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    return paddock

def main():
    token = get_token()
    paddocks = fetch_paddocks()
    results = []
    for p in paddocks:
        if "geometry" not in p:
            continue
        try:
            results.append(fetch_ndvi_for_paddock(p, token))
        except Exception as e:
            print("Error fetching NDVI for", p.get("paddock_name"), e)

    # Save CSV
    keys = ["paddock_name", "ndvi", "date_utc"]
    with open(CSV_OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)

if __name__ == "__main__":
    main()
