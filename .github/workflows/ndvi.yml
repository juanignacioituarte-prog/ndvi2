name: Fetch NDVI

on:
  schedule:
    - cron: "0 6 * * *"  # daily at 6 AM UTC
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests google-cloud-storage

      - name: Run fetch_ndvi.py
        env:
          SH_CLIENT_ID: ${{ secrets.SH_CLIENT_ID }}
          SH_CLIENT_SECRET: ${{ secrets.SH_CLIENT_SECRET }}
          GCS_BUCKET: ndvi-exports
          PADDOCKS_JSON_URL: https://storage.googleapis.com/ndvi-exports/paddocks.json
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCS_SERVICE_ACCOUNT_JSON }}
        run: python fetch_ndvi.py
