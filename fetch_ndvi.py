import json
import os
import requests
from datetime import datetime, timedelta

# ========================
# CONFIG
# ========================
CLIENT_ID = os.environ["SENTINELHUB_CLIENT_ID"]
CLIENT_SECRET = os.environ["SENTINELHUB_CLIENT_SECRET"]

PADOCKS_FILE = "paddocks.json"
OUTPUT_JSON = "paddocks_ndvi.json"
OUTPUT_CSV = "paddocks_ndvi.csv"

TIME_FROM = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
TIME_TO = datetime.utcnow().strftime("%Y-%m-%d")

STATS_URL = "https://services.sentinel-hub.com/api/v1/statistics"
TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"

# ========================
# AUTH
# ========================
def get_token():
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]

TOKEN = get_token()
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ========================
# LOAD PADDOCKS
# ========================
with open(PADOCKS_FILE) as f:
    paddocks = json.load(f)["features"]

results = []

# ========================
# LOOP PADDOCKS
# ========================
for feature in paddocks:
    name = feature["properties"].get("name")
    geometry = feature["geometry"]

    payload = {
        "input": {
            "bounds": {
                "geometry": geometry
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{TIME_FROM}T00:00:00Z",
                        "to": f"{TIME_TO}T23:59:59Z"
                    },
                    "maxCloudCoverage": 80
