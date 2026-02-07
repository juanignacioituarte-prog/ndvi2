import os
import json
import csv
import requests
from google.cloud import storage
from shapely.geometry import shape, mapping
import numpy as np

# --------------------------------------------
# CONFIGURATION
# --------------------------------------------
GCS_BUCKET = "ndvi-exports"
GCS_KEY_JSON = os.environ.get("GCS_SERVICE_ACCOUNT_JSON")
PADDOCKS_GEOJSON = "paddocks.geojson"

# Sentinel Hub
CONFIG_ID = "3d05a814-e5b4-458f-a661-1be8857216a5"  # your SH config ID
SENTINELHUB_URL = "https://services.sentinel-hub.com/api/v1/process"

# Time window for NDVI
TIME_START = "2026-01-01T00:00:00Z"
TIME_END   = "2026-02-06T23:59:59Z"

# --------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------
def get_average_ndvi(geometry):
    """
    Query Sentinel Hub Process API for a given polygon geometry
    and return average NDVI.
    """
    geojson_geom = mapping(shape(geometry))
    # Sentinel Hub evalscript to calculate NDVI
    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: ["B04","B08","dataMask"],
        output: { bands: 1 }
      };
    }
    function evaluatePixel(sample) {
      if (sample.dataMask == 0) return [0];
      let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
      return [ndvi];
    }
    """
    payload = {
        "input": {
            "bounds": {"geometry": geojson_geom},
            "data": [{"type": "S2L2A"}]
        },
        "output": {"width": 512, "height": 512},
        "evalscript": evalscript,
        "time": [TIME_START, TIME_END]
    }
    headers = {"Authorization": f"Bearer {CONFIG_ID}"}
    try:
        r = requests.post(SENTINELHUB_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        # Extract NDVI values from response
        ndvi_values = []
        for row in data.get("data", []):
            ndvi_values.extend(row.get("values", []))
        # Filter zeros (no data) and compute mean
        ndvi_values = [v for v in ndvi_values if v != 0]
        if not ndvi_values:
            return 0.0
        return float(np.mean(ndvi_values))
    except Exception as e:
        print(f"⚠️ NDVI request failed: {e}")
        return 0.0

# --------------------------------------------
# READ PADDOCKS
# --------------------------------------------
with open(PADDOCKS_GEOJSON) as f:
    paddocks_geo = json.load(f)

output_data = []

for feature in paddocks_geo["features"]:
    paddock_name = feature["properties"].get("name")
    if not paddock_name:
        continue
    ndvi = get_average_ndvi(feature["geometry"])
    output_data.append({
        "paddock_name": paddock_name,
        "ndvi": ndvi,
        "date_utc": TIME_END
    })
    print(f"{paddock_name}: NDVI={ndvi:.3f}")

# --------------------------------------------
# EXPORT TO GCS
# --------------------------------------------
client = storage.Client.from_service_account_json(GCS_KEY_JSON)
bucket = client.bucket(GCS_BUCKET)

# JSON
json_blob = bucket.blob("paddocks_ndvi.json")
json_blob.upload_from_string(json.dumps(output_data, indent=2), content_type="application/json")
print("✅ JSON exported to GCS")

# CSV
csv_blob = bucket.blob("paddocks_ndvi.csv")
csv_str = ""
with open("/tmp/tmp.csv", "w", newline="") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=["paddock_name","ndvi","date_utc"])
    writer.writeheader()
    for row in output_data:
        writer.writerow(row)
with open("/tmp/tmp.csv", "rb") as f:
    csv_blob.upload_from_file(f, content_type="text/csv")
print("✅ CSV exported to GCS")
