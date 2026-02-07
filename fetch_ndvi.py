import json
import os
import requests
from datetime import datetime, timedelta
from google.cloud import storage

SH_CLIENT_ID = os.environ["SH_CLIENT_ID"]
SH_CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
GCS_KEYFILE = os.environ["GCS_SERVICE_ACCOUNT_JSON"]
GCS_BUCKET = "ndvi-exports"

PADDocks_FILE = "paddocks.geojson"
OUTPUT_FILE = "paddocks_ndvi.json"

END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=30)

# -----------------------------
# AUTH
# -----------------------------
def get_token():
    r = requests.post(
        "https://services.sentinel-hub.com/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SH_CLIENT_ID,
            "client_secret": SH_CLIENT_SECRET,
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]

TOKEN = get_token()

# -----------------------------
# LOAD PADDOCKS
# -----------------------------
with open(PADDocks_FILE) as f:
    geojson = json.load(f)

features = geojson["features"]

# -----------------------------
# NDVI FETCH
# -----------------------------
def fetch_ndvi(geometry):
    payload = {
        "input": {
            "bounds": {
                "geometry": {
                    "type": "Feature",
                    "geometry": geometry
                }
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{START_DATE}T00:00:00Z",
                            "to": f"{END_DATE}T23:59:59Z",
                        },
                        "maxCloudCoverage": 40,
                    },
                }
            ],
        },
        "aggregation": {
            "timeRange": {
