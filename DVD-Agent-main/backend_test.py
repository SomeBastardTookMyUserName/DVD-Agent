#!/usr/bin/env python3
"""
Backend API Testing for DVD Store Data Collection API
Tests all major endpoints and functionality
"""

import requests
import json
import time
from datetime import datetime
import uuid

# Get backend URL from environment
BACKEND_URL = "https://1f2d1da5-1e8a-405a-9572-23bf9aed1241.preview.emergentagent.com/api"

class DVDStoreAPITester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.test_results = []
        self.created_store_ids = []
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")
    
    def test_root_endpoint(self):
        """Test the root API endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Root Endpoint", True, "API root accessible")
                    return True
                else:
                    self.log_test("Root Endpoint", False, "Unexpected response format", data)
                    return False
            else:
                self.log_test("Root Endpoint", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Connection error: {str(e)}")
            return False
    
    def test_hunter_account(self):
        """Test Hunter.io account integration"""
        try:
            response = self.session.get(f"{self.base_url}/hunter/account")
            if response.status_code == 200:
                data = response.json()
                if "account_info" in data and "credits_remaining" in data:
                    self.log_test("Hunter.io Account", True, f"Account info retrieved, credits: {data.get('credits_remaining', 'unknown')}")
                    return True
                else:
                    self.log_test("Hunter.io Account", False, "Missing expected fields in response", data)
                    return False
            else:
                self.log_test("Hunter.io Account", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Hunter.io Account", False, f"Request error: {str(e)}")
            return False
    
    def test_create_store(self):
        """Test creating a new DVD store"""
        try:
            store_data = {
                "name": "Vintage Video Palace",
                "address": "123 Main Street",
                "city": "Los Angeles",
                "state": "CA",
                "phone": "(555) 123-4567",
                "website": "https://vintagevideopalace.com",
                "source": "manual",
                "notes": "Test store created by automated testing"
            }
            
            response = self.session.post(f"{self.base_url}/stores", json=store_data)
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["name"] == store_data["name"]:
                    self.created_store_ids.append(data["id"])
                    self.log_test("Create Store", True, f"Store created with ID: {data['id']}")
                    return data["id"]
                else:
                    self.log_test("Create Store", False, "Invalid response format", data)
                    return None
            else:
                self.log_test("Create Store", False, f"HTTP {response.status_code}", response.text)
                return None
        except Exception as e:
            self.log_test("Create Store", False, f"Request error: {str(e)}")
            return None
    
    def test_get_stores(self):
        """Test retrieving stores with filtering"""
        try:
            # Test basic get all stores
            response = self.session.get(f"{self.base_url}/stores")
            if response.status_code == 200:
                stores = response.json()
                if isinstance(stores, list):
                    self.log_test("Get All Stores", True, f"Retrieved {len(stores)} stores")
                    
                    # Test with search filter
                    response = self.session.get(f"{self.base_url}/stores?search=Vintage")
                    if response.status_code == 200:
                        filtered_stores = response.json()
                        self.log_test("Get Stores with Search", True, f"Search returned {len(filtered_stores)} stores")
                        
                        # Test with state filter
                        response = self.session.get(f"{self.base_url}/stores?state=CA")
                        if response.status_code == 200:
                            state_stores = response.json()
                            self.log_test("Get Stores by State", True, f"State filter returned {len(state_stores)} stores")
                            return True
                        else:
                            self.log_test("Get Stores by State", False, f"HTTP {response.status_code}", response.text)
                            return False
                    else:
                        self.log_test("Get Stores with Search", False, f"HTTP {response.status_code}", response.text)
                        return False
                else:
                    self.log_test("Get All Stores", False, "Response is not a list", stores)
                    return False
            else:
                self.log_test("Get All Stores", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Get Stores", False, f"Request error: {str(e)}")
            return False
    
    def test_update_store(self, store_id):
        """Test updating a store"""
        if not store_id:
            self.log_test("Update Store", False, "No store ID provided")
            return False
            
        try:
            update_data = {
                "name": "Updated Vintage Video Palace",
                "address": "456 Updated Street",
                "city": "Los Angeles",
                "state": "CA",
                "phone": "(555) 987-6543",
                "website": "https://updatedvintagevideopalace.com",
                "source": "manual",
                "notes": "Updated by automated testing"
            }
            
            response = self.session.put(f"{self.base_url}/stores/{store_id}", json=update_data)
            if response.status_code == 200:
                data = response.json()
                if data["name"] == update_data["name"]:
                    self.log_test("Update Store", True, f"Store {store_id} updated successfully")
                    return True
                else:
                    self.log_test("Update Store", False, "Store not updated properly", data)
                    return False
            else:
                self.log_test("Update Store", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Update Store", False, f"Request error: {str(e)}")
            return False
    
    def test_verify_store(self, store_id):
        """Test verifying a store"""
        if not store_id:
            self.log_test("Verify Store", False, "No store ID provided")
            return False
            
        try:
            response = self.session.post(f"{self.base_url}/stores/{store_id}/verify")
            if response.status_code == 200:
                data = response.json()
                if data.get("verified") == True:
                    self.log_test("Verify Store", True, f"Store {store_id} verified successfully")
                    return True
                else:
                    self.log_test("Verify Store", False, "Store verification failed", data)
                    return False
            else:
                self.log_test("Verify Store", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Verify Store", False, f"Request error: {str(e)}")
            return False
    
    def test_directory_search(self):
        """Test directory search job creation"""
        try:
            search_params = {
                "query": "DVD store",
                "location": "California",
                "max_results": 10
            }
            
            response = self.session.post(f"{self.base_url}/search/directory", params=search_params)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and "status" in data:
                    self.log_test("Directory Search", True, f"Search job created: {data['job_id']}")
                    return data["job_id"]
                else:
                    self.log_test("Directory Search", False, "Invalid response format", data)
                    return None
            else:
                self.log_test("Directory Search", False, f"HTTP {response.status_code}", response.text)
                return None
        except Exception as e:
            self.log_test("Directory Search", False, f"Request error: {str(e)}")
            return None
    
    def test_reddit_search(self):
        """Test Reddit search job creation"""
        try:
            search_params = {
                "query": "DVD store recommendations",
                "max_posts": 20
            }
            
            response = self.session.post(f"{self.base_url}/search/reddit", params=search_params)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and "status" in data:
                    self.log_test("Reddit Search", True, f"Reddit search job created: {data['job_id']}")
                    return data["job_id"]
                else:
                    self.log_test("Reddit Search", False, "Invalid response format", data)
                    return None
            else:
                self.log_test("Reddit Search", False, f"HTTP {response.status_code}", response.text)
                return None
        except Exception as e:
            self.log_test("Reddit Search", False, f"Request error: {str(e)}")
            return None
    
    def test_email_discovery(self):
        """Test email discovery job creation"""
        try:
            # Use created store IDs if available
            payload = {}
            if self.created_store_ids:
                payload["store_ids"] = self.created_store_ids[:1]  # Test with one store
            
            response = self.session.post(f"{self.base_url}/search/emails", json=payload)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and "status" in data:
                    self.log_test("Email Discovery", True, f"Email discovery job created: {data['job_id']}")
                    return data["job_id"]
                else:
                    self.log_test("Email Discovery", False, "Invalid response format", data)
                    return None
            else:
                self.log_test("Email Discovery", False, f"HTTP {response.status_code}", response.text)
                return None
        except Exception as e:
            self.log_test("Email Discovery", False, f"Request error: {str(e)}")
            return None
    
    def test_get_jobs(self):
        """Test retrieving search jobs"""
        try:
            response = self.session.get(f"{self.base_url}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                if isinstance(jobs, list):
                    self.log_test("Get Jobs", True, f"Retrieved {len(jobs)} jobs")
                    return True
                else:
                    self.log_test("Get Jobs", False, "Response is not a list", jobs)
                    return False
            else:
                self.log_test("Get Jobs", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Get Jobs", False, f"Request error: {str(e)}")
            return False
    
    def test_get_stats(self):
        """Test statistics endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                stats = response.json()
                expected_fields = ["total_stores", "verified_stores", "stores_with_emails", "active_jobs", "credits_remaining"]
                if all(field in stats for field in expected_fields):
                    self.log_test("Get Statistics", True, f"Stats retrieved: {stats['total_stores']} total stores")
                    return True
                else:
                    missing_fields = [field for field in expected_fields if field not in stats]
                    self.log_test("Get Statistics", False, f"Missing fields: {missing_fields}", stats)
                    return False
            else:
                self.log_test("Get Statistics", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Get Statistics", False, f"Request error: {str(e)}")
            return False
    
    def test_delete_store(self, store_id):
        """Test deleting a store"""
        if not store_id:
            self.log_test("Delete Store", False, "No store ID provided")
            return False
            
        try:
            response = self.session.delete(f"{self.base_url}/stores/{store_id}")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Delete Store", True, f"Store {store_id} deleted successfully")
                    return True
                else:
                    self.log_test("Delete Store", False, "Unexpected response format", data)
                    return False
            else:
                self.log_test("Delete Store", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_test("Delete Store", False, f"Request error: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            # Test invalid store ID
            response = self.session.get(f"{self.base_url}/stores/invalid-id")
            # This should return 200 with empty list or 404, both are acceptable
            
            # Test invalid job ID
            response = self.session.get(f"{self.base_url}/jobs/invalid-job-id")
            if response.status_code == 404:
                self.log_test("Error Handling", True, "Proper 404 for invalid job ID")
                return True
            else:
                self.log_test("Error Handling", False, f"Expected 404, got {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Error Handling", False, f"Request error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"🚀 Starting DVD Store API Tests")
        print(f"Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Basic connectivity
        if not self.test_root_endpoint():
            print("❌ Cannot connect to API, stopping tests")
            return self.generate_summary()
        
        # Hunter.io integration
        self.test_hunter_account()
        
        # Store CRUD operations
        store_id = self.test_create_store()
        self.test_get_stores()
        
        if store_id:
            self.test_update_store(store_id)
            self.test_verify_store(store_id)
        
        # Search jobs
        self.test_directory_search()
        self.test_reddit_search()
        self.test_email_discovery()
        self.test_get_jobs()
        
        # Statistics
        self.test_get_stats()
        
        # Error handling
        self.test_error_handling()
        
        # Cleanup - delete test stores
        for store_id in self.created_store_ids:
            self.test_delete_store(store_id)
        
        return self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests/total_tests*100) if total_tests > 0 else 0,
            "results": self.test_results
        }

if __name__ == "__main__":
    tester = DVDStoreAPITester()
    summary = tester.run_all_tests()