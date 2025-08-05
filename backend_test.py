#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for DVD Agent
Tests all backend functionality including CRUD operations, Hunter.io integration, 
web scraping, and background job processing.
"""

import requests
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any

# Configuration
BACKEND_URL = "https://8f3b70cc-9483-481c-9db7-8c1721342c4b.preview.emergentagent.com/api"
TIMEOUT = 30

class DVDAgentTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        self.test_results = []
        self.created_store_ids = []
        self.created_job_ids = []
        
    def log_test(self, test_name: str, success: bool, details: str = "", error: str = ""):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
        print()

    def test_basic_connectivity(self):
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{BACKEND_URL}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Basic API Connectivity", True, f"API responded: {data['message']}")
                    return True
                else:
                    self.log_test("Basic API Connectivity", False, "", "Response missing expected message field")
                    return False
            else:
                self.log_test("Basic API Connectivity", False, "", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Basic API Connectivity", False, "", str(e))
            return False

    def test_hunter_account_info(self):
        """Test Hunter.io account information endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/hunter/account")
            if response.status_code == 200:
                data = response.json()
                if "account_info" in data and "credits_remaining" in data:
                    credits = data.get("credits_remaining", "unknown")
                    plan = data.get("plan_name", "unknown")
                    self.log_test("Hunter.io Account Info", True, 
                                f"Credits: {credits}, Plan: {plan}")
                    return True
                else:
                    self.log_test("Hunter.io Account Info", False, "", 
                                "Response missing expected fields")
                    return False
            else:
                self.log_test("Hunter.io Account Info", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Hunter.io Account Info", False, "", str(e))
            return False

    def test_create_store(self):
        """Test creating a new DVD store"""
        try:
            # Realistic DVD store data
            store_data = {
                "name": "Vintage Video Palace",
                "address": "1234 Main Street",
                "city": "Los Angeles",
                "state": "CA",
                "phone": "(555) 123-4567",
                "website": "https://vintagevideopalace.com",
                "email": "info@vintagevideopalace.com",
                "source": "manual",
                "notes": "Specializes in rare and classic DVDs"
            }
            
            response = self.session.post(f"{BACKEND_URL}/stores", json=store_data)
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["name"] == store_data["name"]:
                    self.created_store_ids.append(data["id"])
                    self.log_test("Create DVD Store", True, 
                                f"Created store: {data['name']} (ID: {data['id']})")
                    return True
                else:
                    self.log_test("Create DVD Store", False, "", 
                                "Response missing expected fields or data mismatch")
                    return False
            else:
                self.log_test("Create DVD Store", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Create DVD Store", False, "", str(e))
            return False

    def test_get_stores(self):
        """Test retrieving stores with filtering"""
        try:
            # Test basic get all stores
            response = self.session.get(f"{BACKEND_URL}/stores")
            if response.status_code == 200:
                stores = response.json()
                if isinstance(stores, list):
                    self.log_test("Get All Stores", True, f"Retrieved {len(stores)} stores")
                    
                    # Test with search filter
                    if stores:
                        response = self.session.get(f"{BACKEND_URL}/stores?search=video")
                        if response.status_code == 200:
                            filtered_stores = response.json()
                            self.log_test("Get Stores with Search Filter", True, 
                                        f"Found {len(filtered_stores)} stores matching 'video'")
                        else:
                            self.log_test("Get Stores with Search Filter", False, "", 
                                        f"HTTP {response.status_code}: {response.text}")
                    
                    return True
                else:
                    self.log_test("Get All Stores", False, "", "Response is not a list")
                    return False
            else:
                self.log_test("Get All Stores", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Get All Stores", False, "", str(e))
            return False

    def test_update_store(self):
        """Test updating a store"""
        if not self.created_store_ids:
            self.log_test("Update Store", False, "", "No store ID available for testing")
            return False
            
        try:
            store_id = self.created_store_ids[0]
            update_data = {
                "name": "Vintage Video Palace - Updated",
                "notes": "Updated notes - now also sells Blu-rays"
            }
            
            response = self.session.put(f"{BACKEND_URL}/stores/{store_id}", json=update_data)
            if response.status_code == 200:
                data = response.json()
                if data["name"] == update_data["name"]:
                    self.log_test("Update Store", True, 
                                f"Successfully updated store: {data['name']}")
                    return True
                else:
                    self.log_test("Update Store", False, "", "Update data not reflected in response")
                    return False
            else:
                self.log_test("Update Store", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Update Store", False, "", str(e))
            return False

    def test_verify_store(self):
        """Test verifying a store"""
        if not self.created_store_ids:
            self.log_test("Verify Store", False, "", "No store ID available for testing")
            return False
            
        try:
            store_id = self.created_store_ids[0]
            response = self.session.post(f"{BACKEND_URL}/stores/{store_id}/verify")
            if response.status_code == 200:
                data = response.json()
                if data.get("verified") == True:
                    self.log_test("Verify Store", True, "Store successfully verified")
                    return True
                else:
                    self.log_test("Verify Store", False, "", "Store not marked as verified")
                    return False
            else:
                self.log_test("Verify Store", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Verify Store", False, "", str(e))
            return False

    def test_directory_search_job(self):
        """Test creating a directory search job"""
        try:
            search_params = {
                "query": "DVD store",
                "location": "California",
                "max_results": 10
            }
            
            response = self.session.post(f"{BACKEND_URL}/search/directory", params=search_params)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and data.get("status") == "started":
                    self.created_job_ids.append(data["job_id"])
                    self.log_test("Directory Search Job", True, 
                                f"Started job: {data['job_id']}")
                    return True
                else:
                    self.log_test("Directory Search Job", False, "", 
                                "Response missing expected fields")
                    return False
            else:
                self.log_test("Directory Search Job", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Directory Search Job", False, "", str(e))
            return False

    def test_reddit_search_job(self):
        """Test creating a Reddit search job"""
        try:
            search_params = {
                "query": "best DVD stores",
                "max_posts": 20
            }
            
            response = self.session.post(f"{BACKEND_URL}/search/reddit", params=search_params)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and data.get("status") == "started":
                    self.created_job_ids.append(data["job_id"])
                    self.log_test("Reddit Search Job", True, 
                                f"Started job: {data['job_id']}")
                    return True
                else:
                    self.log_test("Reddit Search Job", False, "", 
                                "Response missing expected fields")
                    return False
            else:
                self.log_test("Reddit Search Job", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Reddit Search Job", False, "", str(e))
            return False

    def test_email_discovery_job(self):
        """Test creating an email discovery job"""
        try:
            # Use created store IDs if available - send as request body list
            job_data = self.created_store_ids[:1] if self.created_store_ids else []
            
            response = self.session.post(f"{BACKEND_URL}/search/emails", json=job_data)
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data and data.get("status") == "started":
                    self.created_job_ids.append(data["job_id"])
                    stores_count = data.get("stores_to_process", 0)
                    self.log_test("Email Discovery Job", True, 
                                f"Started job: {data['job_id']}, processing {stores_count} stores")
                    return True
                else:
                    self.log_test("Email Discovery Job", False, "", 
                                "Response missing expected fields")
                    return False
            else:
                self.log_test("Email Discovery Job", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Email Discovery Job", False, "", str(e))
            return False

    def test_get_jobs(self):
        """Test retrieving search jobs"""
        try:
            response = self.session.get(f"{BACKEND_URL}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                if isinstance(jobs, list):
                    self.log_test("Get Search Jobs", True, f"Retrieved {len(jobs)} jobs")
                    return True
                else:
                    self.log_test("Get Search Jobs", False, "", "Response is not a list")
                    return False
            else:
                self.log_test("Get Search Jobs", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Get Search Jobs", False, "", str(e))
            return False

    def test_get_specific_job(self):
        """Test retrieving a specific job"""
        if not self.created_job_ids:
            self.log_test("Get Specific Job", False, "", "No job ID available for testing")
            return False
            
        try:
            job_id = self.created_job_ids[0]
            response = self.session.get(f"{BACKEND_URL}/jobs/{job_id}")
            if response.status_code == 200:
                job = response.json()
                if job.get("id") == job_id:
                    status = job.get("status", "unknown")
                    job_type = job.get("job_type", "unknown")
                    self.log_test("Get Specific Job", True, 
                                f"Job {job_id}: {job_type} - {status}")
                    return True
                else:
                    self.log_test("Get Specific Job", False, "", "Job ID mismatch")
                    return False
            else:
                self.log_test("Get Specific Job", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Get Specific Job", False, "", str(e))
            return False

    def test_statistics(self):
        """Test getting database statistics"""
        try:
            response = self.session.get(f"{BACKEND_URL}/stats")
            if response.status_code == 200:
                stats = response.json()
                required_fields = ["total_stores", "verified_stores", "stores_with_emails", 
                                 "active_jobs", "credits_remaining"]
                
                if all(field in stats for field in required_fields):
                    details = f"Stores: {stats['total_stores']}, Verified: {stats['verified_stores']}, " \
                             f"With emails: {stats['stores_with_emails']}, Active jobs: {stats['active_jobs']}, " \
                             f"Credits: {stats['credits_remaining']}"
                    self.log_test("Database Statistics", True, details)
                    return True
                else:
                    missing = [f for f in required_fields if f not in stats]
                    self.log_test("Database Statistics", False, "", 
                                f"Missing fields: {missing}")
                    return False
            else:
                self.log_test("Database Statistics", False, "", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Database Statistics", False, "", str(e))
            return False

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            # Test getting non-existent store
            fake_id = str(uuid.uuid4())
            response = self.session.get(f"{BACKEND_URL}/stores/{fake_id}")
            if response.status_code == 404:
                self.log_test("Error Handling - Non-existent Store", True, 
                            "Correctly returned 404 for non-existent store")
            else:
                self.log_test("Error Handling - Non-existent Store", False, "", 
                            f"Expected 404, got {response.status_code}")
                
            # Test invalid store creation
            invalid_store = {"invalid_field": "test"}
            response = self.session.post(f"{BACKEND_URL}/stores", json=invalid_store)
            if response.status_code in [400, 422]:  # Bad request or validation error
                self.log_test("Error Handling - Invalid Store Data", True, 
                            f"Correctly returned {response.status_code} for invalid data")
                return True
            else:
                self.log_test("Error Handling - Invalid Store Data", False, "", 
                            f"Expected 400/422, got {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Error Handling", False, "", str(e))
            return False

    def cleanup_test_data(self):
        """Clean up test data created during testing"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete created stores
        for store_id in self.created_store_ids:
            try:
                response = self.session.delete(f"{BACKEND_URL}/stores/{store_id}")
                if response.status_code == 200:
                    print(f"   ✅ Deleted store: {store_id}")
                else:
                    print(f"   ⚠️  Failed to delete store {store_id}: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Error deleting store {store_id}: {e}")

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting DVD Agent Backend API Tests")
        print(f"🔗 Testing against: {BACKEND_URL}")
        print("=" * 60)
        
        # Core functionality tests
        tests = [
            self.test_basic_connectivity,
            self.test_hunter_account_info,
            self.test_create_store,
            self.test_get_stores,
            self.test_update_store,
            self.test_verify_store,
            self.test_directory_search_job,
            self.test_reddit_search_job,
            self.test_email_discovery_job,
            self.test_get_jobs,
            self.test_get_specific_job,
            self.test_statistics,
            self.test_error_handling
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
                time.sleep(1)  # Brief pause between tests
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
        
        # Wait a bit for background jobs to process
        print("\n⏳ Waiting 5 seconds for background jobs to process...")
        time.sleep(5)
        
        # Cleanup
        self.cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All tests passed! Backend is working correctly.")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Check details above.")
        
        return passed, total, self.test_results

def main():
    """Main test execution"""
    tester = DVDAgentTester()
    passed, total, results = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'passed': passed,
                'total': total,
                'success_rate': (passed/total)*100,
                'timestamp': datetime.now().isoformat()
            },
            'detailed_results': results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)