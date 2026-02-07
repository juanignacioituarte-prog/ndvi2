name: Fetch NDVI

on:
  workflow_dispatch:
  schedule:
    - cron: "0 22 * * *"  # runs daily at 22:00 UTC

jobs:
  fetch-and-upload:
    runs-on: ubuntu-latest

    steps:
    # -------------------------------
    # Step 1: Checkout the repo
    # -------------------------------
    - name: Checkout repo
      uses: actions/checkout@v3

    # -------------------------------
    # Step 2: Setup Python
    # -------------------------------
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    # -------------------------------
    # Step 3: Install dependencies
    # -------------------------------
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests shapely

    # -------------------------------
    # Step 4: Set Sentinel Hub credentials
    # -------------------------------
    - name: Set Sentinel Hub env
      run: |
        echo "SH_CLIENT_ID=${{ secrets.SH_CLIENT_ID }}" >> $GITHUB_ENV
        echo "SH_CLIENT_SECRET=${{ secrets.SH_CLIENT_SECRET }}" >> $GITHUB_ENV

    # -------------------------------
    # Step 5: Set GCS service account
    # -------------------------------
    - name: Configure GCP credentials
      uses: google-github-actions/auth@v1
      with:
        credentials_json: ${{ secrets.GCS_SERVICE_ACCOUNT_JSON }}

    # -------------------------------
    # Step 6: Run fetch_ndvi.py
    # -------------------------------
    - name: Run NDVI fetch
      run: |
        python fetch_ndvi.py

    # -------------------------------
    # Step 7: Upload CSV to GCS
    # -------------------------------
    - name: Upload CSV to GCS
      uses: google-github-actions/upload-cloud-storage@v1
      with:
        path: ./paddocks_ndvi.csv
        destination: paddocks_ndvi.csv
        project_id: your-gcp-project-id
        predefinedAcl: publicRead

    # -------------------------------
    # Step 8: Upload JSON to GCS
    # -------------------------------
    - name: Upload JSON to GCS
      uses: google-github-actions/upload-cloud-storage@v1
      with:
        path: ./paddocks_ndvi.json
        destination: paddocks_ndvi.json
        project_id: your-gcp-project-id
        predefinedAcl: publicRead
