import requests
import json
import csv
import datetime
import os

# -------------------------------
# Environment variables
# -------------------------------
CONFIG_ID = os.environ.get("SH_CONFIG_ID")
if not CONFIG_ID:
    raise ValueError("Environment variable SH_CONFIG_ID not set!")

GCS_BUCKET = os.environ.get("GCS_BUCKET")  # optional
GCS_SERVICE_ACCOUNT_JSON = os.environ.get("GCS_SERVICE_ACCOUNT_JSON")  # optional

TIME_RANGE = {
    "from": "2026-02-01T00:00:00Z",
    "to": "2026-02-05T23:59:59Z"
}

# -------------------------------
# Load paddocks
# -------------------------------
with open("paddocks.geojson") as f:
    paddocks = json.load(f)

ndvi_results = []

# -------------------------------
# Fetch NDVI per paddock
# -------------------------------
for feature in paddocks["features"]:
    geom = feature["geometry"]
    name = feature["properties"]["name"]

    payload = {
        "input": {
            "bounds": geom,
            "data": [{
                "type": "S2L2A",
                "dataFilter": {"timeRange": TIME_RANGE},
                "processing": {
                    "evalscript": """
                    //VERSION=3
                    function setup() { return {input:["B04","B08"], output:{bands:1}}; }
                    function evaluatePixel(sample) { return [(sample.B08 - sample.B04)/(sample.B08 + sample.B04)]; }
                    """
                }
            }]
        },
        "aggregation": {"type": "SIMPLE"}
    }

    response = requests.post(
        f"https://services.sentinel-hub.com/api/v1/statistics/{CONFIG_ID}",
        json=payload
    )
    data = response.json()
    mean_ndvi = data.get("result", {}).get("mean", None)

    ndvi_results.append({
        "paddock_name": name,
        "ndvi": mean_ndvi,
        "date_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })

# -------------------------------
# Save JSON
# -------------------------------
json_file = "paddocks_ndvi.json"
with open(json_file, "w") as f:
    json.dump(ndvi_results, f, indent=2)
print(f"✅ NDVI JSON saved: {json_file}")

# -------------------------------
# Save CSV
# -------------------------------
csv_file = "paddocks_ndvi.csv"
with open(csv_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["paddock_name", "ndvi", "date_utc"])
    writer.writeheader()
    writer.writerows(ndvi_results)
print(f"✅ NDVI CSV saved: {csv_file}")

# -------------------------------
# Optional: Upload to GCS
# -------------------------------
if GCS_BUCKET and GCS_SERVICE_ACCOUNT_JSON:
    # Install google-cloud-storage in requirements.txt
    from google.cloud import storage

    # Write the service account JSON to temporary file
    with open("gcs_key.json", "w") as f:
        f.write(GCS_SERVICE_ACCOUNT_JSON)

    client = storage.Client.from_service_account_json("gcs_key.json")
    bucket = client.bucket(GCS_BUCKET)

    for file in [json_file, csv_file]:
        blob = bucket.blob(file)
        blob.upload_from_filename(file)
        print(f"✅ Uploaded {file} to GCS bucket: {GCS_BUCKET}/{file}")
