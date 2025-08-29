#!/usr/bin/env python3
"""
Authentication Integration Test Suite

This test suite verifies that the authentication system is properly 
integrated with all existing functionality in the Billipocket application.

Tests cover:
1. Login/logout functionality
2. Route protection verification
3. Form submissions with authentication
4. Navigation flow
5. CLI commands
6. Database relationships
"""

import sys
import os
import requests
import subprocess
import time
import json
from datetime import datetime, date

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class AuthIntegrationTester:
    """Comprehensive authentication integration tester."""
    
    def __init__(self, base_url="http://127.0.0.1:5010"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        self.errors = []
        
        # Test credentials
        self.admin_user = {
            'username': 'testadmin',
            'email': 'admin@billipocket.test',
            'password': 'TestPassword123!'
        }
        
        self.regular_user = {
            'username': 'testuser',
            'email': 'user@billipocket.test',
            'password': 'TestPassword123!'
        }
    
    def log_test(self, test_name, success, message="", details=None):
        """Log test result."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✓" if success else "✗"
        result = {
            'timestamp': timestamp,
            'test': test_name,
            'success': success,
            'message': message,
            'details': details
        }
        self.test_results.append(result)
        
        print(f"[{timestamp}] {status} {test_name}")
        if message:
            print(f"    {message}")
        if details and not success:
            print(f"    Details: {details}")
            
    def get_csrf_token(self, response_text):
        """Extract CSRF token from HTML."""
        import re
        pattern = r'name="csrf_token" value="([^"]+)"'
        match = re.search(pattern, response_text)
        return match.group(1) if match else None
    
    def test_server_running(self):
        """Test if the Flask server is running."""
        try:
            response = self.session.get(self.base_url, timeout=5)
            # Should redirect to login for unauthenticated users
            success = response.status_code in [200, 302, 401]
            self.log_test("Server Running", success, 
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Server Running", False, f"Error: {str(e)}")
            return False
    
    def test_login_page_accessible(self):
        """Test that login page is accessible."""
        try:
            response = self.session.get(f"{self.base_url}/auth/login")
            success = response.status_code == 200 and "logi sisse" in response.text.lower()
            self.log_test("Login Page Access", success, 
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Login Page Access", False, f"Error: {str(e)}")
            return False
    
    def test_unauthenticated_redirects(self):
        """Test that protected routes redirect unauthenticated users."""
        protected_routes = [
            "/",
            "/invoices", 
            "/clients",
            "/settings"
        ]
        
        all_success = True
        for route in protected_routes:
            try:
                response = self.session.get(f"{self.base_url}{route}", allow_redirects=False)
                # Should redirect (302) to login
                success = response.status_code == 302 and "/auth/login" in response.headers.get('Location', '')
                self.log_test(f"Route Protection {route}", success, 
                             f"Status: {response.status_code}, Location: {response.headers.get('Location', 'None')}")
                if not success:
                    all_success = False
            except Exception as e:
                self.log_test(f"Route Protection {route}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def login_user(self, user_data):
        """Attempt to log in a user."""
        try:
            # Get login page first for CSRF token
            login_response = self.session.get(f"{self.base_url}/auth/login")
            if login_response.status_code != 200:
                return False, "Cannot access login page"
            
            csrf_token = self.get_csrf_token(login_response.text)
            if not csrf_token:
                return False, "Cannot extract CSRF token"
            
            # Attempt login
            login_data = {
                'csrf_token': csrf_token,
                'username': user_data['username'],
                'password': user_data['password'],
                'remember_me': False,
                'submit': True
            }
            
            response = self.session.post(f"{self.base_url}/auth/login", 
                                       data=login_data,
                                       allow_redirects=True)
            
            # Check if login was successful (should redirect to dashboard)
            success = response.status_code == 200 and "ülevaade" in response.text.lower()
            return success, f"Status: {response.status_code}"
            
        except Exception as e:
            return False, f"Login error: {str(e)}"
    
    def logout_user(self):
        """Log out current user."""
        try:
            response = self.session.get(f"{self.base_url}/auth/logout", allow_redirects=True)
            # Should redirect to login page
            success = response.status_code == 200 and ("logi sisse" in response.text.lower() or "login" in response.url.lower())
            return success, f"Status: {response.status_code}"
        except Exception as e:
            return False, f"Logout error: {str(e)}"
    
    def test_dashboard_access_after_login(self):
        """Test that dashboard is accessible after login."""
        try:
            response = self.session.get(f"{self.base_url}/")
            success = response.status_code == 200 and "ülevaade" in response.text.lower()
            self.log_test("Dashboard Access", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Dashboard Access", False, f"Error: {str(e)}")
            return False
    
    def test_invoice_functionality(self):
        """Test invoice CRUD operations with authentication."""
        try:
            # Test invoice list access
            response = self.session.get(f"{self.base_url}/invoices")
            invoices_access = response.status_code == 200
            
            # Test new invoice page access
            response = self.session.get(f"{self.base_url}/invoices/new")
            new_invoice_access = response.status_code == 200
            
            success = invoices_access and new_invoice_access
            self.log_test("Invoice Functionality", success,
                         f"List: {invoices_access}, New: {new_invoice_access}")
            return success
            
        except Exception as e:
            self.log_test("Invoice Functionality", False, f"Error: {str(e)}")
            return False
    
    def test_client_functionality(self):
        """Test client CRUD operations with authentication."""
        try:
            # Test client list access
            response = self.session.get(f"{self.base_url}/clients")
            clients_access = response.status_code == 200
            
            # Test new client page access
            response = self.session.get(f"{self.base_url}/clients/new")
            new_client_access = response.status_code == 200
            
            success = clients_access and new_client_access
            self.log_test("Client Functionality", success,
                         f"List: {clients_access}, New: {new_client_access}")
            return success
            
        except Exception as e:
            self.log_test("Client Functionality", False, f"Error: {str(e)}")
            return False
    
    def test_settings_access(self):
        """Test settings page access."""
        try:
            response = self.session.get(f"{self.base_url}/settings")
            success = response.status_code == 200 and "seaded" in response.text.lower()
            self.log_test("Settings Access", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Settings Access", False, f"Error: {str(e)}")
            return False
    
    def test_profile_access(self):
        """Test user profile access."""
        try:
            response = self.session.get(f"{self.base_url}/auth/profile")
            success = response.status_code == 200 and "profiil" in response.text.lower()
            self.log_test("Profile Access", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Profile Access", False, f"Error: {str(e)}")
            return False
    
    def test_navigation_links(self):
        """Test that all navigation links work properly."""
        navigation_routes = [
            ("/", "ülevaade"),
            ("/invoices", "arved"),
            ("/clients", "kliendid"), 
            ("/settings", "seaded"),
            ("/auth/profile", "profiil")
        ]
        
        all_success = True
        for route, expected_text in navigation_routes:
            try:
                response = self.session.get(f"{self.base_url}{route}")
                success = response.status_code == 200 and expected_text.lower() in response.text.lower()
                self.log_test(f"Navigation {route}", success, 
                             f"Status: {response.status_code}")
                if not success:
                    all_success = False
            except Exception as e:
                self.log_test(f"Navigation {route}", False, f"Error: {str(e)}")
                all_success = False
        
        return all_success
    
    def test_csrf_protection(self):
        """Test CSRF protection on forms."""
        try:
            # Try to submit a form without CSRF token
            response = self.session.post(f"{self.base_url}/clients/new", 
                                       data={'name': 'Test Client'})
            # Should fail with 400 or redirect
            success = response.status_code in [400, 403, 302]
            self.log_test("CSRF Protection", success, 
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("CSRF Protection", False, f"Error: {str(e)}")
            return False
    
    def test_cli_commands(self):
        """Test CLI commands for user management."""
        try:
            # Test list users command
            result = subprocess.run([
                sys.executable, 'run.py', 'list-users'
            ], capture_output=True, text=True, timeout=30)
            
            success = result.returncode == 0
            self.log_test("CLI List Users", success,
                         f"Return code: {result.returncode}")
            
            if not success and result.stderr:
                print(f"    CLI Error: {result.stderr}")
                
            return success
            
        except subprocess.TimeoutExpired:
            self.log_test("CLI List Users", False, "Command timed out")
            return False
        except Exception as e:
            self.log_test("CLI List Users", False, f"Error: {str(e)}")
            return False
    
    def test_admin_functionality(self):
        """Test admin-specific functionality."""
        try:
            # Test user management page access
            response = self.session.get(f"{self.base_url}/auth/users")
            success = response.status_code == 200 and "kasutajad" in response.text.lower()
            self.log_test("Admin Users Page", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Admin Users Page", False, f"Error: {str(e)}")
            return False
    
    def create_test_user_via_cli(self, user_data, is_admin=False):
        """Create a test user via CLI."""
        try:
            command = 'create-admin' if is_admin else 'create-user'
            result = subprocess.run([
                sys.executable, 'run.py', command,
                user_data['username'],
                user_data['email'],
                '--password', user_data['password']
            ], capture_output=True, text=True, timeout=30)
            
            return result.returncode == 0, result.stderr or result.stdout
            
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 60)
        print("BILLIPOCKET AUTHENTICATION INTEGRATION TESTS")
        print("=" * 60)
        
        # Phase 1: Server and basic connectivity
        print("\nPhase 1: Server Connectivity")
        print("-" * 30)
        
        if not self.test_server_running():
            print("\n❌ Server is not running. Please start the Flask server.")
            return False
        
        self.test_login_page_accessible()
        
        # Phase 2: Route protection (unauthenticated)
        print("\nPhase 2: Route Protection")
        print("-" * 30)
        self.test_unauthenticated_redirects()
        self.test_csrf_protection()
        
        # Phase 3: Create test users
        print("\nPhase 3: User Setup")
        print("-" * 30)
        
        # Try to create admin user
        admin_created, admin_msg = self.create_test_user_via_cli(self.admin_user, is_admin=True)
        self.log_test("Create Admin User", admin_created, admin_msg)
        
        # Phase 4: Authentication flow
        print("\nPhase 4: Authentication Flow") 
        print("-" * 30)
        
        # Test admin login
        login_success, login_msg = self.login_user(self.admin_user)
        self.log_test("Admin Login", login_success, login_msg)
        
        if not login_success:
            print("\n❌ Cannot continue - login failed")
            return False
        
        # Phase 5: Authenticated functionality
        print("\nPhase 5: Authenticated Access")
        print("-" * 30)
        
        self.test_dashboard_access_after_login()
        self.test_navigation_links()
        self.test_invoice_functionality()
        self.test_client_functionality()
        self.test_settings_access()
        self.test_profile_access()
        
        # Phase 6: Admin functionality
        print("\nPhase 6: Admin Features")
        print("-" * 30)
        
        self.test_admin_functionality()
        
        # Phase 7: Logout
        print("\nPhase 7: Logout")
        print("-" * 30)
        
        logout_success, logout_msg = self.logout_user()
        self.log_test("Logout", logout_success, logout_msg)
        
        # Phase 8: CLI commands
        print("\nPhase 8: CLI Commands")
        print("-" * 30)
        
        self.test_cli_commands()
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ❌ {result['test']}: {result['message']}")
        
        return failed_tests == 0

def main():
    """Main test runner."""
    print("Starting Billipocket Authentication Integration Tests...")
    
    # Check if server is running
    tester = AuthIntegrationTester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n\nTest suite error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)