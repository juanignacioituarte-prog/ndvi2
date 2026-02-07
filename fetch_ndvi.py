import json
import os
import requests
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================

CLIENT_ID = os.environ["SENTINELHUB_CLIENT_ID"]
CLIENT_SECRET = os.environ["SENTINELHUB_CLIENT_SECRET"]

PADDocks_FILE = "paddocks.json"
OUTPUT_FILE = "paddocks_ndvi.json"

TIME_TO = datetime.utcnow().date()
TIME_FROM = TIME_TO - timedelta(days=10)

STATS_URL = "https://services.sentinel-hub.com/api/v1/statistics"
TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"

# =========================
# AUTH
# =========================

def get_token():
    r = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
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

# =========================
# LOAD PADDOCKS
# =========================

with open(PADDocks_FILE, "r") as f:
    paddocks = json.load(f)

results = []

# =========================
# LOOP PADDOCKS
# =========================

for feature in paddocks["features"]:
    name = feature.get("properties", {}).get("name")
    geometry = feature["geometry"]

    payload = {
        "input": {
            "bounds": {
                "geometry": geometry
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{TIME_FROM}T00:00:00Z",
                            "to": f"{TIME_TO}T23:59:59Z",
                        },
                        "maxCloudCoverage": 80,
                    },
                }
            ],
        },
        "aggregation": {
            "timeRange": {
                "from": f"{TIME_FROM}T00:00:00Z",
                "to": f"{TIME_TO}T23:59:59Z",
            },
            "aggregationInterval": {"of": "P1D"},
            "resx": 10,
            "resy": 10,
        },
        "evalscript": """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08"],
    output: [{ id: "ndvi", bands: 1 }]
  };
}

function evaluatePixel(s) {
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);
  return [ndvi];
}
""",
    }

    r = requests.post(STATS_URL, headers=HEADERS, json=payload)

    if r.status_code != 200:
        print(f"⚠️ Failed for {name}: {r.text}")
        ndvi_value = None
    else:
        data = r.json()
        try:
            intervals = data["data"]
            values = [
                d["outputs"]["ndvi"]["stats"]["mean"]
                for d in intervals
                if d["outputs"]["ndvi"]["stats"]["mean"] is not None
            ]
            ndvi_value = round(sum(values) / len(values), 3) if values else None
        except Exception:
            ndvi_value = None

    results.append(
        {
            "paddock_name": name,
            "ndvi": ndvi_value,
            "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

# =========================
# SAVE OUTPUT
# =========================

wi
