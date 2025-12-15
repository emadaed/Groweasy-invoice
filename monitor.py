#!/usr/bin/env python3
"""
Simple monitoring script
Run this on your local machine to monitor production
"""

import requests
import time
from datetime import datetime

def check_health(url):
    """Check application health"""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now()}] ✅ Healthy - Users: {data.get('users', 0)}")
            return True
        else:
            print(f"[{datetime.now()}] ❌ Unhealthy - Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error: {e}")
        return False

if __name__ == '__main__':
    URL = input("Enter your app URL (e.g., https://growe.up.railway.app): ")
    INTERVAL = 300  # Check every 5 minutes

    print(f"🔍 Monitoring {URL} every {INTERVAL} seconds...")
    print("Press Ctrl+C to stop\n")

    while True:
        check_health(URL)
        time.sleep(INTERVAL)
