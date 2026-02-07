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
def get_average_ndvi_batch(geojson_features):
    """
    Query Sentinel Hub Process API once for all paddocks.
    Returns dict {paddock_name: avg_ndvi}.
    """
    ndvi_results = {}

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

    # Create a multi-geometry request
    data_list = [{"type": "S2L2A", "dataFilter": {"maxCloudCoverage": 50}}]
    batch_payload = {
        "input": {
            "bounds": {
                "geometry": {
                    "type": "GeometryCollection",
                    "geometries": [mapping(shape(f["geometry"])) for f in geojson_features]
                }
            },
            "data": data_list
        },
        "output": {"width": 512, "height": 512},
        "evalscript": evalscript,
        "time": [TIME_START, TIME_END]
    }

    headers = {"Authorization": f"Bearer {CONFIG_ID}"}

    try:
        r = requests.post(SENTINELHUB_URL, json=batch_payload, headers=headers)
        r.raise_for_status()
        response = r.json()

        # The response may contain a single raster for all geometries
        ndvi_values = response.get("data", [])

        # Compute average NDVI per paddock
        for idx, feature in enumerate(geojson_features):
            values = ndvi_values[idx]["values"] if idx < len(ndvi_values) else []
            values = [v for v in values if v != 0]
            avg_ndvi = float(np.mean(values)) if values else 0.0
            ndvi_results[feature["properties"]["name"]] = avg_ndvi

        return ndvi_results

    except Exception as e:
        print(f"⚠️ Sentinel Hub batch request failed: {e}")
        # fallback 0
        return {f["properties"]["name"]: 0.0 for f in geojson_features}

# --------------------------------------------
# READ PADDOCKS
# --------------------------------------------
with open(PADDOCKS_GEOJSON) as f:
    paddocks_geo = json.load(f)

# Batch request
ndvi_dict = get_average_ndvi_batch(paddocks_geo["features"])

# Prepare output
output_data = []
for feature in paddocks_geo["features"]:
    paddock_name = feature["properties"].get("name")
    if not paddock_name:
        continue
    ndvi = ndvi_dict.get(paddock_name, 0.0)
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
