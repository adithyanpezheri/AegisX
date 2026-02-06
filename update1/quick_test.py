import sys
import time
time.sleep(2)

import requests
import json

BASE_URL = "http://127.0.0.1:5000"

print("Testing API connection...")
for attempt in range(3):
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=5)
        print(f"✓ API Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        break
    except Exception as e:
        print(f"✗ Attempt {attempt+1}: {str(e)[:80]}")
        if attempt < 2:
            time.sleep(2)
