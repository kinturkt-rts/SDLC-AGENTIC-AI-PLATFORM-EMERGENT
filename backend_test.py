#!/usr/bin/env python3
"""
Comprehensive backend API test suite for SDLC Agentic Platform Control Plane.
Tests MCP Registry CRUD, Projects API, and Health endpoints.
"""

import requests
import json
import sys
from typing import Dict, Any, List

# Base URL from environment
BASE_URL = "https://dynamic-repo-load.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def pass_test(self, test_name: str):
        self.passed += 1
        print(f"✅ PASS: {test_name}")
    
    def fail_test(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed, {self.failed}/{total} failed")
        print(f"{'='*80}")
        if self.errors:
            print("\nFailed Tests:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0

result = TestResult()

def test_get_mcp_initial():
    """Test 1: GET /api/mcp returns 200 with mcpServers containing >= 7 servers"""
    print("\n[Test 1] GET /api/mcp - Initial seed with 7 servers")
    try:
        response = requests.get(f"{API_BASE}/mcp", timeout=10)
        
        if response.status_code != 200:
            result.fail_test("GET /api/mcp status", f"Expected 200, got {response.status_code}")
            return None
        
        data = response.json()
        
        if "mcpServers" not in data:
            result.fail_test("GET /api/mcp structure", "Missing 'mcpServers' key in response")
            return None
        
        servers = data["mcpServers"]
        if not isinstance(servers, dict):
            result.fail_test("GET /api/mcp structure", "mcpServers is not an object")
            return None
        
        server_count = len(servers)
        if server_count < 7:
            result.fail_test("GET /api/mcp server count", f"Expected >= 7 servers, got {server_count}")
            return None
        
        # Check for required servers
        required_servers = ["Atlassian", "GitLab", "Postgres", "MongoDB", "Firecrawl", "AWS Diagram", "Terraform"]
        missing = [s for s in required_servers if s not in servers]
        if missing:
            result.fail_test("GET /api/mcp required servers", f"Missing servers: {missing}")
            return None
        
        # Verify each server has required fields
        for name, config in servers.items():
            if not isinstance(config, dict):
                result.fail_test("GET /api/mcp server config", f"Server '{name}' config is not an object")
                return None
            # Check for command/args/type or url
            has_command = "command" in config
            has_url = "url" in config
            if not has_command and not has_url:
                result.fail_test("GET /api/mcp server config", f"Server '{name}' has neither command nor url")
                return None
        
        result.pass_test("GET /api/mcp - Initial seed with 7 servers")
        print(f"   Found {server_count} servers: {list(servers.keys())}")
        return data
    
    except Exception as e:
        result.fail_test("GET /api/mcp", f"Exception: {str(e)}")
        return None

def test_validate_raw_secret_rejected():
    """Test 2a: POST /api/mcp/validate rejects raw secrets"""
    print("\n[Test 2a] POST /api/mcp/validate - Reject raw secret")
    try:
        payload = {
            "name": "TestServer",
            "config": {
                "command": "npx",
                "env": {
                    "K": "sk-rawsecret"
                }
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp/validate", json=payload, timeout=10)
        
        if response.status_code != 200:
            result.fail_test("POST /api/mcp/validate (raw secret) status", f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        if "valid" not in data:
            result.fail_test("POST /api/mcp/validate (raw secret) structure", "Missing 'valid' key")
            return
        
        if data["valid"] != False:
            result.fail_test("POST /api/mcp/validate (raw secret) validation", f"Expected valid=false, got {data['valid']}")
            return
        
        if "errors" not in data or not isinstance(data["errors"], list) or len(data["errors"]) == 0:
            result.fail_test("POST /api/mcp/validate (raw secret) errors", "Expected non-empty errors array")
            return
        
        # Check that error mentions secret reference
        error_text = " ".join(data["errors"]).lower()
        if "secret" not in error_text and "reference" not in error_text:
            result.fail_test("POST /api/mcp/validate (raw secret) error message", f"Error should mention secret reference: {data['errors']}")
            return
        
        result.pass_test("POST /api/mcp/validate - Reject raw secret")
        print(f"   Errors: {data['errors']}")
    
    except Exception as e:
        result.fail_test("POST /api/mcp/validate (raw secret)", f"Exception: {str(e)}")

def test_validate_reference_accepted():
    """Test 2b: POST /api/mcp/validate accepts secret references"""
    print("\n[Test 2b] POST /api/mcp/validate - Accept secret reference")
    try:
        payload = {
            "name": "TestServer",
            "config": {
                "command": "npx",
                "env": {
                    "K": "${env:K}"
                }
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp/validate", json=payload, timeout=10)
        
        if response.status_code != 200:
            result.fail_test("POST /api/mcp/validate (reference) status", f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        if "valid" not in data:
            result.fail_test("POST /api/mcp/validate (reference) structure", "Missing 'valid' key")
            return
        
        if data["valid"] != True:
            result.fail_test("POST /api/mcp/validate (reference) validation", f"Expected valid=true, got {data['valid']}. Errors: {data.get('errors', [])}")
            return
        
        if "errors" not in data or not isinstance(data["errors"], list):
            result.fail_test("POST /api/mcp/validate (reference) structure", "Missing or invalid 'errors' array")
            return
        
        if len(data["errors"]) > 0:
            result.fail_test("POST /api/mcp/validate (reference) errors", f"Expected empty errors, got {data['errors']}")
            return
        
        result.pass_test("POST /api/mcp/validate - Accept secret reference")
    
    except Exception as e:
        result.fail_test("POST /api/mcp/validate (reference)", f"Exception: {str(e)}")

def test_validate_no_command_no_url():
    """Test 2c: POST /api/mcp/validate rejects config with no command and no url"""
    print("\n[Test 2c] POST /api/mcp/validate - Reject no command, no url")
    try:
        payload = {
            "name": "TestServer",
            "config": {
                "env": {
                    "K": "${env:K}"
                }
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp/validate", json=payload, timeout=10)
        
        if response.status_code != 200:
            result.fail_test("POST /api/mcp/validate (no command) status", f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        if data.get("valid") != False:
            result.fail_test("POST /api/mcp/validate (no command) validation", f"Expected valid=false, got {data.get('valid')}")
            return
        
        if not data.get("errors") or len(data["errors"]) == 0:
            result.fail_test("POST /api/mcp/validate (no command) errors", "Expected non-empty errors array")
            return
        
        result.pass_test("POST /api/mcp/validate - Reject no command, no url")
        print(f"   Errors: {data['errors']}")
    
    except Exception as e:
        result.fail_test("POST /api/mcp/validate (no command)", f"Exception: {str(e)}")

def test_validate_url_only_valid():
    """Test 2d: POST /api/mcp/validate accepts url-only remote server"""
    print("\n[Test 2d] POST /api/mcp/validate - Accept url-only remote server")
    try:
        payload = {
            "name": "RemoteServer",
            "config": {
                "url": "https://remote.example",
                "type": "http"
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp/validate", json=payload, timeout=10)
        
        if response.status_code != 200:
            result.fail_test("POST /api/mcp/validate (url-only) status", f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        if data.get("valid") != True:
            result.fail_test("POST /api/mcp/validate (url-only) validation", f"Expected valid=true, got {data.get('valid')}. Errors: {data.get('errors', [])}")
            return
        
        if len(data.get("errors", [])) > 0:
            result.fail_test("POST /api/mcp/validate (url-only) errors", f"Expected empty errors, got {data['errors']}")
            return
        
        result.pass_test("POST /api/mcp/validate - Accept url-only remote server")
    
    except Exception as e:
        result.fail_test("POST /api/mcp/validate (url-only)", f"Exception: {str(e)}")

def test_add_valid_server():
    """Test 3a: POST /api/mcp adds valid server"""
    print("\n[Test 3a] POST /api/mcp - Add valid server")
    try:
        payload = {
            "name": "SmokeTestServer",
            "config": {
                "command": "npx",
                "args": ["-y", "x"],
                "env": {
                    "TOKEN": "${env:TOKEN}"
                },
                "type": "stdio",
                "disabled": False
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp", json=payload, timeout=10)
        
        if response.status_code != 200:
            result.fail_test("POST /api/mcp (valid add) status", f"Expected 200, got {response.status_code}. Body: {response.text}")
            return False
        
        data = response.json()
        
        if not data.get("ok"):
            result.fail_test("POST /api/mcp (valid add) response", f"Expected ok=true, got {data.get('ok')}")
            return False
        
        if data.get("name") != "SmokeTestServer":
            result.fail_test("POST /api/mcp (valid add) name", f"Expected name='SmokeTestServer', got {data.get('name')}")
            return False
        
        if "mcpServers" not in data:
            result.fail_test("POST /api/mcp (valid add) structure", "Missing 'mcpServers' in response")
            return False
        
        if "SmokeTestServer" not in data["mcpServers"]:
            result.fail_test("POST /api/mcp (valid add) server presence", "SmokeTestServer not in mcpServers")
            return False
        
        result.pass_test("POST /api/mcp - Add valid server")
        return True
    
    except Exception as e:
        result.fail_test("POST /api/mcp (valid add)", f"Exception: {str(e)}")
        return False

def test_add_invalid_server():
    """Test 3b: POST /api/mcp rejects invalid server with raw secret"""
    print("\n[Test 3b] POST /api/mcp - Reject invalid server (raw secret)")
    try:
        payload = {
            "name": "BadServer",
            "config": {
                "command": "npx",
                "env": {
                    "TOKEN": "plainsecret"
                }
            }
        }
        
        response = requests.post(f"{API_BASE}/mcp", json=payload, timeout=10)
        
        if response.status_code != 400:
            result.fail_test("POST /api/mcp (invalid add) status", f"Expected 400, got {response.status_code}")
            return
        
        data = response.json()
        
        if "errors" not in data or not isinstance(data["errors"], list) or len(data["errors"]) == 0:
            result.fail_test("POST /api/mcp (invalid add) errors", f"Expected non-empty errors array, got {data}")
            return
        
        # Verify BadServer is NOT in the registry
        get_response = requests.get(f"{API_BASE}/mcp", timeout=10)
        if get_response.status_code == 200:
            get_data = get_response.json()
            if "BadServer" in get_data.get("mcpServers", {}):
                result.fail_test("POST /api/mcp (invalid add) persistence", "BadServer should NOT be in registry after rejection")
                return
        
        result.pass_test("POST /api/mcp - Reject invalid server (raw secret)")
        print(f"   Errors: {data['errors']}")
    
    except Exception as e:
        result.fail_test("POST /api/mcp (invalid add)", f"Exception: {str(e)}")

def test_persistence():
    """Test 4: Verify persistence - add, GET (present), DELETE, GET (absent)"""
    print("\n[Test 4] Persistence - Add, verify, delete, verify absent")
    try:
        # First, verify SmokeTestServer is present (from test 3a)
        get_response = requests.get(f"{API_BASE}/mcp", timeout=10)
        if get_response.status_code != 200:
            result.fail_test("Persistence (GET after add) status", f"Expected 200, got {get_response.status_code}")
            return
        
        get_data = get_response.json()
        if "SmokeTestServer" not in get_data.get("mcpServers", {}):
            result.fail_test("Persistence (GET after add)", "SmokeTestServer not found after add")
            return
        
        print("   ✓ SmokeTestServer present after add")
        
        # Delete SmokeTestServer
        delete_response = requests.delete(f"{API_BASE}/mcp/SmokeTestServer", timeout=10)
        if delete_response.status_code != 200:
            result.fail_test("Persistence (DELETE) status", f"Expected 200, got {delete_response.status_code}")
            return
        
        delete_data = delete_response.json()
        if not delete_data.get("ok"):
            result.fail_test("Persistence (DELETE) response", f"Expected ok=true, got {delete_data.get('ok')}")
            return
        
        print("   ✓ DELETE returned ok=true")
        
        # Verify SmokeTestServer is absent
        get_response2 = requests.get(f"{API_BASE}/mcp", timeout=10)
        if get_response2.status_code != 200:
            result.fail_test("Persistence (GET after delete) status", f"Expected 200, got {get_response2.status_code}")
            return
        
        get_data2 = get_response2.json()
        if "SmokeTestServer" in get_data2.get("mcpServers", {}):
            result.fail_test("Persistence (GET after delete)", "SmokeTestServer still present after delete")
            return
        
        print("   ✓ SmokeTestServer absent after delete")
        
        result.pass_test("Persistence - Add, verify, delete, verify absent")
    
    except Exception as e:
        result.fail_test("Persistence", f"Exception: {str(e)}")

def test_delete_nonexistent():
    """Test 5: DELETE /api/mcp/NonExistentXYZ returns 404"""
    print("\n[Test 5] DELETE /api/mcp/NonExistentXYZ - 404 for missing server")
    try:
        response = requests.delete(f"{API_BASE}/mcp/NonExistentXYZ", timeout=10)
        
        if response.status_code != 404:
            result.fail_test("DELETE nonexistent server status", f"Expected 404, got {response.status_code}")
            return
        
        data = response.json()
        if "error" not in data:
            result.fail_test("DELETE nonexistent server response", "Expected 'error' key in response")
            return
        
        result.pass_test("DELETE /api/mcp/NonExistentXYZ - 404 for missing server")
        print(f"   Error: {data['error']}")
    
    except Exception as e:
        result.fail_test("DELETE nonexistent server", f"Exception: {str(e)}")

def test_get_projects():
    """Test 6: GET /api/v1/projects returns 7 projects with no environment field"""
    print("\n[Test 6] GET /api/v1/projects - 7 projects, no environment field")
    try:
        response = requests.get(f"{API_BASE}/v1/projects", timeout=10)
        
        if response.status_code != 200:
            result.fail_test("GET /api/v1/projects status", f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        if "projects" not in data:
            result.fail_test("GET /api/v1/projects structure", "Missing 'projects' key")
            return
        
        projects = data["projects"]
        if not isinstance(projects, list):
            result.fail_test("GET /api/v1/projects structure", "projects is not an array")
            return
        
        if len(projects) != 7:
            result.fail_test("GET /api/v1/projects count", f"Expected exactly 7 projects, got {len(projects)}")
            return
        
        # Check for required slugs
        slugs = [p.get("slug") for p in projects]
        if "customer-feedback-hub" not in slugs:
            result.fail_test("GET /api/v1/projects slugs", "Missing 'customer-feedback-hub'")
            return
        
        if "meeting-action-tracker" not in slugs:
            result.fail_test("GET /api/v1/projects slugs", "Missing 'meeting-action-tracker'")
            return
        
        # Verify NO environment field
        for project in projects:
            if "environment" in project:
                result.fail_test("GET /api/v1/projects environment field", f"Project {project.get('slug')} has 'environment' field (should be omitted)")
                return
        
        # Verify required fields
        for project in projects:
            required_fields = ["slug", "name"]
            missing = [f for f in required_fields if f not in project]
            if missing:
                result.fail_test("GET /api/v1/projects fields", f"Project missing fields: {missing}")
                return
        
        result.pass_test("GET /api/v1/projects - 7 projects, no environment field")
        print(f"   Slugs: {slugs}")
    
    except Exception as e:
        result.fail_test("GET /api/v1/projects", f"Exception: {str(e)}")

def test_health_endpoints():
    """Test 7: GET /api/health and GET /api return correct service name"""
    print("\n[Test 7] Health endpoints - service='sdlc-agentic-platform'")
    try:
        # Test GET /api/health
        health_response = requests.get(f"{API_BASE}/health", timeout=10)
        if health_response.status_code != 200:
            result.fail_test("GET /api/health status", f"Expected 200, got {health_response.status_code}")
            return
        
        health_data = health_response.json()
        
        if health_data.get("service") != "sdlc-agentic-platform":
            result.fail_test("GET /api/health service", f"Expected service='sdlc-agentic-platform', got '{health_data.get('service')}'")
            return
        
        if health_data.get("status") != "ok":
            result.fail_test("GET /api/health status field", f"Expected status='ok', got '{health_data.get('status')}'")
            return
        
        if health_data.get("mode") != "mock":
            result.fail_test("GET /api/health mode", f"Expected mode='mock', got '{health_data.get('mode')}'")
            return
        
        if "time" not in health_data:
            result.fail_test("GET /api/health time", "Missing 'time' field")
            return
        
        print("   ✓ GET /api/health passed")
        
        # Test GET /api (root)
        root_response = requests.get(f"{API_BASE}", timeout=10)
        if root_response.status_code != 200:
            result.fail_test("GET /api status", f"Expected 200, got {root_response.status_code}")
            return
        
        root_data = root_response.json()
        
        if root_data.get("service") != "sdlc-agentic-platform":
            result.fail_test("GET /api service", f"Expected service='sdlc-agentic-platform', got '{root_data.get('service')}'")
            return
        
        if root_data.get("status") != "ok":
            result.fail_test("GET /api status field", f"Expected status='ok', got '{root_data.get('status')}'")
            return
        
        if root_data.get("mode") != "mock":
            result.fail_test("GET /api mode", f"Expected mode='mock', got '{root_data.get('mode')}'")
            return
        
        print("   ✓ GET /api passed")
        
        result.pass_test("Health endpoints - service='sdlc-agentic-platform'")
    
    except Exception as e:
        result.fail_test("Health endpoints", f"Exception: {str(e)}")

def test_catch_all_404():
    """Test 8: GET /api/does-not-exist returns 404"""
    print("\n[Test 8] GET /api/does-not-exist - 404 for unknown route")
    try:
        response = requests.get(f"{API_BASE}/does-not-exist", timeout=10)
        
        if response.status_code != 404:
            result.fail_test("GET /api/does-not-exist status", f"Expected 404, got {response.status_code}")
            return
        
        data = response.json()
        if "error" not in data:
            result.fail_test("GET /api/does-not-exist response", "Expected 'error' key in response")
            return
        
        result.pass_test("GET /api/does-not-exist - 404 for unknown route")
        print(f"   Error: {data['error']}")
    
    except Exception as e:
        result.fail_test("GET /api/does-not-exist", f"Exception: {str(e)}")

def cleanup():
    """Cleanup: Ensure SmokeTestServer and BadServer are removed"""
    print("\n[Cleanup] Removing test artifacts")
    try:
        # Try to delete SmokeTestServer (may already be deleted)
        requests.delete(f"{API_BASE}/mcp/SmokeTestServer", timeout=10)
        
        # Try to delete BadServer (should not exist, but just in case)
        requests.delete(f"{API_BASE}/mcp/BadServer", timeout=10)
        
        # Verify clean state
        response = requests.get(f"{API_BASE}/mcp", timeout=10)
        if response.status_code == 200:
            data = response.json()
            servers = data.get("mcpServers", {})
            if "SmokeTestServer" in servers or "BadServer" in servers:
                print("   ⚠️  Warning: Test artifacts still present after cleanup")
            else:
                print("   ✓ Cleanup successful - test artifacts removed")
    except Exception as e:
        print(f"   ⚠️  Cleanup exception: {str(e)}")

def main():
    print("="*80)
    print("BACKEND API TEST SUITE - SDLC Agentic Platform Control Plane")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print("="*80)
    
    # Run all tests in order
    test_get_mcp_initial()
    test_validate_raw_secret_rejected()
    test_validate_reference_accepted()
    test_validate_no_command_no_url()
    test_validate_url_only_valid()
    
    # Test 3a must succeed for test 4 to work
    if test_add_valid_server():
        test_persistence()
    else:
        print("\n⚠️  Skipping persistence test due to add failure")
    
    test_add_invalid_server()
    test_delete_nonexistent()
    test_get_projects()
    test_health_endpoints()
    test_catch_all_404()
    
    # Cleanup
    cleanup()
    
    # Summary
    success = result.summary()
    
    if success:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
