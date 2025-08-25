#!/usr/bin/env python3
"""
Comprehensive verification test script for BilliPocket Flask application
Tests all key functionalities after database status system fixes
"""

import requests
import json
from datetime import datetime, date
import sys

BASE_URL = "http://localhost:5010"

class BilliPocketTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = {}
        
    def test_dashboard(self):
        """Test dashboard page loads and displays correct data"""
        print("Testing Dashboard...")
        try:
            response = self.session.get(f"{BASE_URL}/")
            if response.status_code == 200:
                content = response.text
                # Check for key dashboard elements
                checks = {
                    "dashboard_title": "Ülevaade" in content,
                    "unpaid_section": "Maksmata arved" in content,
                    "recent_invoices": "Viimased arved" in content,
                    "financial_metrics": "Käive" in content,
                    "financial_totals": "€" in content  # Check for currency symbols
                }
                self.test_results["dashboard"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Dashboard test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["dashboard"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Dashboard test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["dashboard"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Dashboard test: ERROR - {e}")
    
    def test_invoice_listing(self):
        """Test invoice listing page"""
        print("Testing Invoice Listing...")
        try:
            response = self.session.get(f"{BASE_URL}/invoices")
            if response.status_code == 200:
                content = response.text
                checks = {
                    "invoice_list": "Arved" in content,
                    "status_badges": "maksmata" in content or "makstud" in content,
                    "action_buttons": "Vaata" in content or "Muuda" in content,
                    "create_button": "Loo uus arve" in content
                }
                self.test_results["invoice_listing"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Invoice listing test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["invoice_listing"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Invoice listing test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["invoice_listing"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Invoice listing test: ERROR - {e}")
    
    def test_invoice_creation_form(self):
        """Test invoice creation form loads"""
        print("Testing Invoice Creation Form...")
        try:
            response = self.session.get(f"{BASE_URL}/invoices/new")
            if response.status_code == 200:
                content = response.text
                checks = {
                    "form_present": '<form' in content,
                    "client_field": 'name="client_id"' in content,
                    "date_fields": 'name="date"' in content and 'name="due_date"' in content,
                    "csrf_token": 'name="csrf_token"' in content,
                    "submit_button": 'type="submit"' in content
                }
                self.test_results["invoice_creation"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Invoice creation form test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["invoice_creation"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Invoice creation form test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["invoice_creation"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Invoice creation form test: ERROR - {e}")
    
    def test_client_listing(self):
        """Test client listing page"""
        print("Testing Client Listing...")
        try:
            response = self.session.get(f"{BASE_URL}/clients")
            if response.status_code == 200:
                content = response.text
                checks = {
                    "client_list": "Kliendid" in content,
                    "create_button": "Lisa uus klient" in content,
                    "client_data": "Geopol" in content or "client" in content.lower()
                }
                self.test_results["client_listing"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Client listing test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["client_listing"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Client listing test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["client_listing"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Client listing test: ERROR - {e}")
    
    def test_specific_invoice_view(self):
        """Test viewing a specific invoice"""
        print("Testing Specific Invoice View...")
        try:
            # Test with invoice ID 1
            response = self.session.get(f"{BASE_URL}/invoices/1")
            if response.status_code == 200:
                content = response.text
                checks = {
                    "invoice_details": "Arve" in content and ("2025-" in content),
                    "client_info": "Geopol" in content or "client" in content.lower(),
                    "status_display": "maksmata" in content or "makstud" in content,
                    "edit_button": "Muuda" in content or "Edit" in content,
                    "pdf_button": "PDF" in content
                }
                self.test_results["invoice_view"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Invoice view test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["invoice_view"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Invoice view test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["invoice_view"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Invoice view test: ERROR - {e}")
    
    def test_settings_page(self):
        """Test settings page loads"""
        print("Testing Settings Page...")
        try:
            response = self.session.get(f"{BASE_URL}/settings")
            if response.status_code == 200:
                content = response.text
                checks = {
                    "settings_title": "Seaded" in content,
                    "form_present": '<form' in content,
                    "company_fields": 'name="company_name"' in content,
                    "save_button": 'type="submit"' in content
                }
                self.test_results["settings"] = {
                    "status": "PASS" if all(checks.values()) else "FAIL",
                    "details": checks,
                    "response_code": response.status_code
                }
                print(f"✓ Settings test: {'PASS' if all(checks.values()) else 'FAIL'}")
            else:
                self.test_results["settings"] = {
                    "status": "FAIL",
                    "details": f"HTTP {response.status_code}",
                    "response_code": response.status_code
                }
                print(f"✗ Settings test: FAIL (HTTP {response.status_code})")
        except Exception as e:
            self.test_results["settings"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Settings test: ERROR - {e}")
    
    def check_database_status_consistency(self):
        """Check that database only contains valid status values"""
        print("Testing Database Status Consistency...")
        try:
            import sqlite3
            conn = sqlite3.connect('/Users/keijovalting/Downloads/billipocket_gpt5/instance/billipocket.db')
            cursor = conn.cursor()
            
            # Check all status values in database
            cursor.execute("SELECT DISTINCT status FROM invoices")
            statuses = [row[0] for row in cursor.fetchall()]
            
            # Valid statuses in the 2-status system
            valid_statuses = ['maksmata', 'makstud']
            
            invalid_statuses = [s for s in statuses if s not in valid_statuses]
            
            self.test_results["database_status"] = {
                "status": "PASS" if not invalid_statuses else "FAIL",
                "details": {
                    "found_statuses": statuses,
                    "invalid_statuses": invalid_statuses,
                    "valid_statuses": valid_statuses
                }
            }
            
            conn.close()
            print(f"✓ Database status consistency: {'PASS' if not invalid_statuses else 'FAIL'}")
            if invalid_statuses:
                print(f"  Invalid statuses found: {invalid_statuses}")
            
        except Exception as e:
            self.test_results["database_status"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Database status consistency: ERROR - {e}")
    
    def generate_report(self):
        """Generate final test report"""
        print("\n" + "="*60)
        print("BILLIPOCKET VERIFICATION TEST REPORT")
        print("="*60)
        print(f"Test executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        failed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'FAIL')
        error_tests = sum(1 for result in self.test_results.values() if result['status'] == 'ERROR')
        
        print(f"SUMMARY:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {failed_tests}")
        print(f"  Errors: {error_tests}")
        print(f"  Success Rate: {(passed_tests/total_tests*100):.1f}%")
        print()
        
        print("DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status_symbol = {
                'PASS': '✓',
                'FAIL': '✗',
                'ERROR': '⚠'
            }.get(result['status'], '?')
            
            print(f"  {status_symbol} {test_name.upper()}: {result['status']}")
            if result['status'] != 'PASS':
                print(f"    Details: {result.get('details', 'No details')}")
        
        print("\n" + "="*60)
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run all verification tests"""
        print("Starting BilliPocket verification tests...\n")
        
        self.test_dashboard()
        self.test_invoice_listing()
        self.test_invoice_creation_form()
        self.test_client_listing()
        self.test_specific_invoice_view()
        self.test_settings_page()
        self.check_database_status_consistency()
        
        return self.generate_report()

if __name__ == "__main__":
    tester = BilliPocketTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)