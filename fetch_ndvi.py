import json
import os
import requests
from datetime import datetime, timedelta
from google.cloud import storage

# -----------------------------
# CONFIG
# -----------------------------
SH_CLIENT_ID = os.environ["SH_CLIENT_ID"]
SH_CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
GCS_BUCKET = "ndvi-exports"

PADDocks_FILE = "paddocks.geojson"
OUTPUT_FILE = "paddocks_ndvi.json"

# last 30 days
END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=30)

# -----------------------------
# AUTH: Sentinel Hub
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
# NDVI STATS API CALL
# -----------------------------
def fetch_ndvi(geometry):
    payload = {
        "input": {
            "bounds": {"geometry": geometry},
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
                "from": f"{START_DATE}T00:00:00Z",
                "to": f"{END_DATE}T23:59:59Z",
            },
            "aggregationInterval": {"of": "P1D"},
            "evalscript": """
            //VERSION=3
            function setup() {
              return {
                input: ["B04", "B08", "dataMask"],
                output: [{ id: "ndvi", bands: 1 }]
              };
            }

            function evaluatePixel(sample) {
              if (sample.dataMask === 0) {
                return { ndvi: [NaN] };
              }
              let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
              return { ndvi: [ndvi] };
            }
            """,
        },
        "calculations": {
            "ndvi": {
                "statistics": {
                    "default": {"mean": True}
                }
            }
        },
    }

    r = requests.post(
        "https://services.sentinel-hub.com/api/v1/statistics",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if r.status_code != 200:
        print("Stats API error:", r.text)
        return None

    data = r.json()["data"]

    values = []
    for day in data:
        stats = day["outputs"]["ndvi"]["stats"]
        if stats["mean"] is not None:
            values.append(stats["mean"])

    if not values:
        return None

    return round(sum(values) / len(values), 3)

# -----------------------------
# PROCESS ALL PADDOCKS
# -----------------------------
results = []

for f in features:
    name = f["properties"].get("name")
    geom = f["geometry"]

    ndvi = fetch_ndvi(geom)

    results.append({
        "paddock_name": name,
        "ndvi": ndvi,
        "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    })

# -----------------------------
# SAVE + UPLOAD TO GCS
# -----------------------------
with open(OUTPUT_FILE, "w") as f:
    json.dump(results, f, indent=2)

client = storage.Client.from_service_account_json(
    os.environ["GCS_SERVICE_ACCOUNT_JSON"]
)
bucket = client.bucket(GCS_BUCKET)
blob = bucket.blob(OUTPUT_FILE)
blob.upload_from_filename(OUTPUT_FILE, content_type="application/json")

print("✅ NDVI export complete")
