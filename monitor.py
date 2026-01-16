# monitor.py - Automatic health monitoring
import requests
import time
from datetime import datetime

RAILWAY_URL = "https://growe.up.railway.app"

def check_endpoint(endpoint, expected_status=200):
    try:
        url = f"{RAILWAY_URL}{endpoint}"
        response = requests.get(url, timeout=10)

        if response.status_code == expected_status:
            return True, f"✅ {endpoint}: {response.status_code}"
        else:
            return False, f"❌ {endpoint}: {response.status_code} (expected {expected_status})"

    except Exception as e:
        return False, f"❌ {endpoint}: ERROR - {str(e)}"

def run_health_checks():
    print(f"\n🕐 Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    endpoints = [
        ("/health", 200),
        ("/", 200),
        ("/login", 200),
        ("/register", 200),
        ("/about", 200),
        ("/terms", 200),
    ]

    all_ok = True
    for endpoint, expected in endpoints:
        ok, message = check_endpoint(endpoint, expected)
        print(message)
        if not ok:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("🎉 ALL SYSTEMS OPERATIONAL")
    else:
        print("⚠️ SOME ISSUES DETECTED")

    return all_ok

if __name__ == "__main__":
    # Run every 5 minutes
    while True:
        run_health_checks()
        time.sleep(300)  # 5 minutes
