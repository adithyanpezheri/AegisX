import requests
import json

BASE_URL = "http://127.0.0.1:5000"

# Test 1: Check API status
print("=" * 50)
print("TEST 1: API Status")
print("=" * 50)
try:
    response = requests.get(f"{BASE_URL}/api/status")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("TEST 2: Upload Dataset")
print("=" * 50)
try:
    with open("test_dataset.csv", "rb") as f:
        files = {"file": f}
        response = requests.post(f"{BASE_URL}/api/upload", files=files)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    filepath = response.json().get('filepath')
except Exception as e:
    print(f"Error: {e}")
    filepath = None

if filepath:
    print("\n" + "=" * 50)
    print("TEST 3: Train Model (Autoencoder)")
    print("=" * 50)
    try:
        data = {
            "filepath": filepath,
            "model_type": "autoencoder"
        }
        response = requests.post(f"{BASE_URL}/api/train", json=data)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 50)
    print("TEST 4: Train Model (Isolation Forest)")
    print("=" * 50)
    try:
        data = {
            "filepath": filepath,
            "model_type": "isolation_forest"
        }
        response = requests.post(f"{BASE_URL}/api/train", json=data)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 50)
    print("TEST 5: Predict/Analyze")
    print("=" * 50)
    try:
        data = {
            "filepath": filepath
        }
        response = requests.post(f"{BASE_URL}/api/predict", json=data)
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "=" * 50)
print("TEST 6: List Models")
print("=" * 50)
try:
    response = requests.get(f"{BASE_URL}/api/list_models")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\nAPI Tests Complete!")
