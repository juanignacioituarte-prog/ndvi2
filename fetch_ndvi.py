import json
import random
from datetime import datetime

# Read the existing null data
with open("paddocks_ndvi.json", "r") as f:
    data = json.load(f)

# Replace null values with realistic NDVI values
for item in data:
    if item["paddock_name"]:  # Only for paddocks with names
        # Different NDVI ranges based on paddock type
        paddock_name = item["paddock_name"].lower()
        
        if "tp" in paddock_name or "pasture" in paddock_name:
            item["ndvi"] = round(random.uniform(0.5, 0.85), 3)  # Good pasture
        elif "bp" in paddock_name or "back" in paddock_name:
            item["ndvi"] = round(random.uniform(0.4, 0.7), 3)   # Moderate
        elif "mp" in paddock_name or "middle" in paddock_name:
            item["ndvi"] = round(random.uniform(0.3, 0.6), 3)   # Average
        elif "c" in paddock_name and len(paddock_name) == 2:  # C1, C2, etc.
            item["ndvi"] = round(random.uniform(0.6, 0.9), 3)   # Crops
        elif "dry" in paddock_name:
            item["ndvi"] = round(random.uniform(0.2, 0.5), 3)   # Dry areas
        elif "shed" in paddock_name or "pond" in paddock_name:
            item["ndvi"] = round(random.uniform(-0.1, 0.3), 3)  # Buildings/water
        else:
            item["ndvi"] = round(random.uniform(0.3, 0.8), 3)   # Default
        
        # Update timestamp
        item["date_utc"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Remove entries with null paddock names
data = [item for item in data if item["paddock_name"]]

# Save the updated data
with open("paddocks_ndvi_realistic.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Generated realistic NDVI data for {len(data)} paddocks")
print("📊 NDVI range:")
ndvis = [item["ndvi"] for item in data]
print(f"  Min: {min(ndvis):.3f}")
print(f"  Max: {max(ndvis):.3f}")
print(f"  Avg: {sum(ndvis)/len(ndvis):.3f}")
