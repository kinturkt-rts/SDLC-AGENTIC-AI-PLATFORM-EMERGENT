"""QA Edge case tests for contacts-api.

Tests boundary conditions and edge cases not covered in developer baseline.
Follows PRD FR-* requirements and design §4/§5 constraints.
"""
import pytest
from fastapi.testclient import TestClient


class TestAuthEdgeCases:
    """Test API key authentication edge cases."""
    
    def test_wrong_api_key(self, client: TestClient, seeded_dept):
        """Test with incorrect API key returns 401."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Test User",
            "email": "test@company.com"
        }
        response = client.post("/contacts/", json=contact_data, 
                             headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]
    
    def test_api_key_case_sensitivity(self, client: TestClient, seeded_dept):
        """Test API key is case sensitive."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Test User", 
            "email": "test@company.com"
        }
        response = client.post("/contacts/", json=contact_data,
                             headers={"X-API-Key": "TEST-KEY"})  # uppercase
        assert response.status_code == 401


class TestValidationEdgeCases:
    """Test input validation boundary conditions."""
    
    def test_contact_empty_name(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test contact creation with empty name fails."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "",
            "email": "test@company.com"
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_contact_long_name(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test contact creation with name > 120 chars fails."""
        long_name = "A" * 121  # Exceeds 120 char limit per design
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": long_name,
            "email": "test@company.com"
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_contact_long_phone(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test contact creation with phone > 30 chars fails.""" 
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Test User",
            "email": "test@company.com",
            "phone": "1" * 31  # Exceeds 30 char limit
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_contact_long_title(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test contact creation with title > 80 chars fails."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Test User", 
            "email": "test@company.com",
            "title": "A" * 81  # Exceeds 80 char limit
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_department_empty_name(self, client: TestClient, api_headers: dict):
        """Test department creation with empty name fails."""
        dept_data = {"name": "", "code": "ENG"}
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_department_long_name(self, client: TestClient, api_headers: dict):
        """Test department creation with name > 80 chars fails."""
        dept_data = {"name": "A" * 81, "code": "ENG"}
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_department_code_too_short(self, client: TestClient, api_headers: dict):
        """Test department creation with code < 2 chars fails."""
        dept_data = {"name": "Engineering", "code": "E"}
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_department_code_too_long(self, client: TestClient, api_headers: dict):
        """Test department creation with code > 10 chars fails."""
        dept_data = {"name": "Engineering", "code": "ENGINEERING"}  # 11 chars
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 422
    
    def test_department_code_lowercase(self, client: TestClient, api_headers: dict):
        """Test department creation with lowercase code fails."""
        dept_data = {"name": "Engineering", "code": "eng"}
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 422


class TestPaginationEdgeCases:
    """Test pagination boundary conditions."""
    
    def test_contacts_limit_max_boundary(self, client: TestClient):
        """Test contacts pagination limit at max boundary (100)."""
        response = client.get("/contacts/?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 100
    
    def test_contacts_limit_exceeds_max(self, client: TestClient):
        """Test contacts pagination limit > 100 returns validation error."""
        response = client.get("/contacts/?limit=200")
        assert response.status_code == 422  # Validation error is correct
    
    def test_contacts_negative_limit(self, client: TestClient):
        """Test contacts pagination with negative limit returns validation error."""
        response = client.get("/contacts/?limit=-1")
        assert response.status_code == 422  # Validation error is correct
    
    def test_contacts_negative_offset(self, client: TestClient):
        """Test contacts pagination with negative offset returns validation error."""
        response = client.get("/contacts/?offset=-1")
        assert response.status_code == 422  # Validation error is correct
    
    def test_contacts_zero_limit(self, client: TestClient):
        """Test contacts pagination with zero limit returns validation error."""
        response = client.get("/contacts/?limit=0")
        assert response.status_code == 422  # Validation error is correct (ge=1)


class TestSearchEdgeCases:
    """Test search functionality edge cases."""
    
    def test_search_empty_query(self, client: TestClient, seeded_contact):
        """Test search with empty query returns all."""
        response = client.get("/contacts/?q=")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0  # Should work with empty query
    
    def test_search_special_characters(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test search with special characters."""
        # Create contact with special chars
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "O'Brien-Smith",
            "email": "o.brien-smith@company.com"
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 201
        
        # Search should handle special chars
        response = client.get("/contacts/?q=O'Brien")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
    
    def test_search_very_long_query(self, client: TestClient):
        """Test search with very long query string."""
        long_query = "a" * 1000
        response = client.get(f"/contacts/?q={long_query}")
        assert response.status_code == 200  # Should not crash
    
    def test_search_case_insensitive(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test search is case insensitive per design."""
        # Create contact
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Alice Smith",
            "email": "alice.smith@company.com"
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 201
        
        # Search with different cases should find it
        for query in ["alice", "ALICE", "Alice", "SMITH", "smith"]:
            response = client.get(f"/contacts/?q={query}")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 1


class TestActiveStatusEdgeCases:
    """Test is_active field behavior."""
    
    def test_inactive_contacts_still_searchable(self, client: TestClient, api_headers: dict, seeded_contact):
        """Test inactive contacts appear in search results."""
        # Soft delete the contact
        response = client.delete(f"/contacts/{seeded_contact.id}", headers=api_headers)
        assert response.status_code == 204
        
        # Search should still find it
        response = client.get("/contacts/?q=John")
        assert response.status_code == 200
        data = response.json()
        # Should find the inactive contact
        inactive_found = any(
            contact["id"] == seeded_contact.id and not contact["is_active"] 
            for contact in data["items"]
        )
        assert inactive_found
    
    def test_inactive_contacts_in_list(self, client: TestClient, api_headers: dict, seeded_contact):
        """Test inactive contacts appear in list endpoint."""
        # Soft delete the contact
        response = client.delete(f"/contacts/{seeded_contact.id}", headers=api_headers)
        assert response.status_code == 204
        
        # List should still include it
        response = client.get("/contacts/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        # Find the inactive contact
        inactive_found = any(
            contact["id"] == seeded_contact.id and not contact["is_active"]
            for contact in data["items"]
        )
        assert inactive_found


class TestNullableFieldEdgeCases:
    """Test optional field handling."""
    
    def test_contact_minimal_fields(self, client: TestClient, api_headers: dict, seeded_dept):
        """Test contact creation with only required fields."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Minimal User",
            "email": "minimal@company.com"
            # phone and title are optional
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 201
        
        contact = response.json()
        assert contact["full_name"] == "Minimal User"
        assert contact["email"] == "minimal@company.com"
        assert contact["phone"] is None
        assert contact["title"] is None
    
    def test_contact_update_clear_optional_fields(self, client: TestClient, api_headers: dict, seeded_contact):
        """Test updating contact to clear optional fields."""
        update_data = {
            "phone": None,
            "title": None
        }
        response = client.patch(f"/contacts/{seeded_contact.id}", json=update_data, headers=api_headers)
        assert response.status_code == 200
        
        contact = response.json()
        assert contact["phone"] is None
        assert contact["title"] is None


class TestErrorResponseFormat:
    """Test error response consistency."""
    
    def test_404_error_format(self, client: TestClient):
        """Test 404 errors have consistent format."""
        response = client.get("/contacts/99999999-9999-9999-9999-999999999999")
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)
    
    def test_401_error_format(self, client: TestClient, seeded_dept):
        """Test 401 errors have consistent format."""
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": "Test User",
            "email": "test@company.com"
        }
        response = client.post("/contacts/", json=contact_data)
        assert response.status_code == 401
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)
    
    def test_409_error_format(self, client: TestClient, api_headers: dict, seeded_contact):
        """Test 409 conflict errors have consistent format."""
        contact_data = {
            "department_id": seeded_contact.department_id,
            "full_name": "Different Name",
            "email": seeded_contact.email  # duplicate email
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 409
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)