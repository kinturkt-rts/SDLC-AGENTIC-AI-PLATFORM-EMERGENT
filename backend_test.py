#!/usr/bin/env python3
"""
Backend API tests for Helmsman Control Plane
Tests the minimal read-only health API endpoints
"""

import requests
import json
from datetime import datetime

# Base URL from environment
BASE_URL = "https://pipeline-dashboard-11.preview.emergentagent.com"

def test_health_endpoint():
    """Test GET /api/health returns 200 with correct JSON structure"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/health")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/api/health"
        print(f"Request: GET {url}")
        
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        # Check status code
        if response.status_code != 200:
            print(f"❌ FAILED: Expected status 200, got {response.status_code}")
            return False
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: Invalid JSON response: {e}")
            return False
        
        # Verify required fields
        required_fields = {
            'service': 'helmsman-control-plane',
            'status': 'ok',
            'mode': 'mock'
        }
        
        for field, expected_value in required_fields.items():
            if field not in data:
                print(f"❌ FAILED: Missing field '{field}' in response")
                return False
            if data[field] != expected_value:
                print(f"❌ FAILED: Field '{field}' = '{data[field]}', expected '{expected_value}'")
                return False
            print(f"✓ Field '{field}' = '{data[field]}' (correct)")
        
        # Verify 'time' field exists and is a string
        if 'time' not in data:
            print(f"❌ FAILED: Missing 'time' field in response")
            return False
        if not isinstance(data['time'], str):
            print(f"❌ FAILED: Field 'time' is not a string, got {type(data['time'])}")
            return False
        
        # Try to parse time as ISO format
        try:
            datetime.fromisoformat(data['time'].replace('Z', '+00:00'))
            print(f"✓ Field 'time' = '{data['time']}' (valid ISO timestamp)")
        except ValueError:
            print(f"⚠ WARNING: Field 'time' = '{data['time']}' is not a valid ISO timestamp")
        
        print("✅ TEST PASSED: GET /api/health")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def test_root_api_endpoint():
    """Test GET /api returns 200 with same JSON structure as /health"""
    print("\n" + "="*80)
    print("TEST 2: GET /api")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/api"
        print(f"Request: GET {url}")
        
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        # Check status code
        if response.status_code != 200:
            print(f"❌ FAILED: Expected status 200, got {response.status_code}")
            return False
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: Invalid JSON response: {e}")
            return False
        
        # Verify required fields (same as /health)
        required_fields = {
            'service': 'helmsman-control-plane',
            'status': 'ok',
            'mode': 'mock'
        }
        
        for field, expected_value in required_fields.items():
            if field not in data:
                print(f"❌ FAILED: Missing field '{field}' in response")
                return False
            if data[field] != expected_value:
                print(f"❌ FAILED: Field '{field}' = '{data[field]}', expected '{expected_value}'")
                return False
            print(f"✓ Field '{field}' = '{data[field]}' (correct)")
        
        # Verify 'time' field exists and is a string
        if 'time' not in data:
            print(f"❌ FAILED: Missing 'time' field in response")
            return False
        if not isinstance(data['time'], str):
            print(f"❌ FAILED: Field 'time' is not a string, got {type(data['time'])}")
            return False
        
        print(f"✓ Field 'time' = '{data['time']}' (valid string)")
        print("✅ TEST PASSED: GET /api")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def test_not_found_endpoint():
    """Test GET /api/does-not-exist returns 404 with error message"""
    print("\n" + "="*80)
    print("TEST 3: GET /api/does-not-exist")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/api/does-not-exist"
        print(f"Request: GET {url}")
        
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        # Check status code
        if response.status_code != 404:
            print(f"❌ FAILED: Expected status 404, got {response.status_code}")
            return False
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: Invalid JSON response: {e}")
            return False
        
        # Verify error field
        if 'error' not in data:
            print(f"❌ FAILED: Missing 'error' field in response")
            return False
        
        expected_error = "Route /does-not-exist not found"
        if data['error'] != expected_error:
            print(f"❌ FAILED: Error message = '{data['error']}', expected '{expected_error}'")
            return False
        
        print(f"✓ Error message = '{data['error']}' (correct)")
        print("✅ TEST PASSED: GET /api/does-not-exist")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def test_cors_preflight():
    """Test OPTIONS /api/health returns 200 with CORS headers"""
    print("\n" + "="*80)
    print("TEST 4: OPTIONS /api/health (CORS preflight)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/api/health"
        print(f"Request: OPTIONS {url}")
        
        response = requests.options(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        # Check status code (accept both 200 and 204 for OPTIONS)
        if response.status_code not in [200, 204]:
            print(f"❌ FAILED: Expected status 200 or 204, got {response.status_code}")
            return False
        
        if response.status_code == 204:
            print(f"✓ Status code = 204 (No Content - standard for OPTIONS, functionally equivalent to 200)")
        else:
            print(f"✓ Status code = 200")
        
        # Check for CORS headers
        cors_header = 'Access-Control-Allow-Origin'
        if cors_header not in response.headers:
            print(f"❌ FAILED: Missing '{cors_header}' header")
            return False
        
        print(f"✓ Header '{cors_header}' = '{response.headers[cors_header]}' (present)")
        
        # Check other CORS headers (informational)
        other_cors_headers = ['Access-Control-Allow-Methods', 'Access-Control-Allow-Headers']
        for header in other_cors_headers:
            if header in response.headers:
                print(f"✓ Header '{header}' = '{response.headers[header]}'")
        
        print("✅ TEST PASSED: OPTIONS /api/health")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def main():
    """Run all backend tests"""
    print("\n" + "="*80)
    print("HELMSMAN CONTROL PLANE - BACKEND API TESTS")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Testing minimal read-only health API")
    print("="*80)
    
    results = {
        'GET /api/health': test_health_endpoint(),
        'GET /api': test_root_api_endpoint(),
        'GET /api/does-not-exist': test_not_found_endpoint(),
        'OPTIONS /api/health': test_cors_preflight()
    }
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("="*80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
