#!/usr/bin/env python3
"""
Pre-deployment test script
Run this before deploying to production
"""

import requests
import sys

def test_health_check(base_url):
    """Test health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_login_page(base_url):
    """Test login page loads"""
    try:
        response = requests.get(f"{base_url}/login", timeout=5)
        if response.status_code == 200 and 'GrowEasy Invoice' in response.text:
            print("✅ Login page loads correctly")
            return True
        else:
            print("❌ Login page failed")
            return False
    except Exception as e:
        print(f"❌ Login page error: {e}")
        return False

def test_static_files(base_url):
    """Test static files load"""
    try:
        response = requests.get(f"{base_url}/static/css/bootstrap.min.css", timeout=5)
        if response.status_code == 200:
            print("✅ Static files working")
            return True
        else:
            print("❌ Static files failed")
            return False
    except Exception as e:
        print(f"❌ Static files error: {e}")
        return False

if __name__ == '__main__':
    # Test local or production
    base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'

    print(f"🧪 Testing deployment at: {base_url}\n")

    tests = [
        test_health_check(base_url),
        test_login_page(base_url),
        test_static_files(base_url)
    ]

    if all(tests):
        print("\n✅ All tests passed! Ready to deploy.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Fix before deploying.")
        sys.exit(1)
