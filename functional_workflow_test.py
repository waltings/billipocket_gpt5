#!/usr/bin/env python3
"""
Comprehensive functional workflow test for BilliPocket
Tests complete user workflows including data persistence and status transitions
"""

import requests
import sqlite3
from datetime import datetime, date
import sys
import re
from urllib.parse import urljoin

BASE_URL = "http://localhost:5010"
DB_PATH = "/Users/keijovalting/Downloads/billipocket_gpt5/instance/billipocket.db"

class WorkflowTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = {}
        
    def get_csrf_token(self, url):
        """Extract CSRF token from a form page"""
        response = self.session.get(url)
        if response.status_code != 200:
            return None
        
        # Look for CSRF token in the HTML
        csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]*)"', response.text)
        return csrf_match.group(1) if csrf_match else None
    
    def test_database_status_system(self):
        """Test that database status system is working correctly"""
        print("Testing Database Status System...")
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Test 1: Check that only valid statuses exist
            cursor.execute("SELECT DISTINCT status FROM invoices")
            statuses = [row[0] for row in cursor.fetchall()]
            valid_statuses = ['maksmata', 'makstud']
            invalid_statuses = [s for s in statuses if s not in valid_statuses]
            
            # Test 2: Count invoices by status
            cursor.execute("SELECT status, COUNT(*) FROM invoices GROUP BY status")
            status_counts = dict(cursor.fetchall())
            
            # Test 3: Verify totals calculation
            cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'maksmata'")
            unpaid_total = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'makstud'")
            paid_total = cursor.fetchone()[0] or 0
            
            conn.close()
            
            self.test_results["database_status_system"] = {
                "status": "PASS" if not invalid_statuses else "FAIL",
                "details": {
                    "statuses_found": statuses,
                    "invalid_statuses": invalid_statuses,
                    "status_counts": status_counts,
                    "unpaid_total": float(unpaid_total),
                    "paid_total": float(paid_total)
                }
            }
            
            print(f"✓ Database Status System: {'PASS' if not invalid_statuses else 'FAIL'}")
            print(f"  Status counts: {status_counts}")
            print(f"  Unpaid total: {unpaid_total}€")
            print(f"  Paid total: {paid_total}€")
            
        except Exception as e:
            self.test_results["database_status_system"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Database Status System: ERROR - {e}")
    
    def test_invoice_status_transitions(self):
        """Test that invoice status can be changed and persists correctly"""
        print("Testing Invoice Status Transitions...")
        try:
            # Find an unpaid invoice to test with
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, number, status FROM invoices WHERE status = 'maksmata' LIMIT 1")
            result = cursor.fetchone()
            
            if not result:
                print("  No unpaid invoices found to test with")
                self.test_results["status_transitions"] = {
                    "status": "SKIP",
                    "details": "No unpaid invoices available for testing"
                }
                conn.close()
                return
            
            invoice_id, invoice_number, original_status = result
            conn.close()
            
            # Test status change via edit form
            edit_url = f"{BASE_URL}/invoices/{invoice_id}/edit"
            csrf_token = self.get_csrf_token(edit_url)
            
            if not csrf_token:
                self.test_results["status_transitions"] = {
                    "status": "FAIL",
                    "details": "Could not get CSRF token"
                }
                print("✗ Status Transitions: FAIL - No CSRF token")
                return
            
            # Change status to paid
            form_data = {
                'csrf_token': csrf_token,
                'status': 'makstud'
            }
            
            # Get the current form data first
            response = self.session.get(edit_url)
            if response.status_code == 200:
                # Extract current form values
                content = response.text
                
                # Get client_id
                client_match = re.search(r'name="client_id"[^>]*selected[^>]*value="(\d+)"', content)
                if client_match:
                    form_data['client_id'] = client_match.group(1)
                
                # Get dates
                date_match = re.search(r'name="date"[^>]*value="([^"]*)"', content)
                if date_match:
                    form_data['date'] = date_match.group(1)
                
                due_date_match = re.search(r'name="due_date"[^>]*value="([^"]*)"', content)
                if due_date_match:
                    form_data['due_date'] = due_date_match.group(1)
            
            # Submit the form
            response = self.session.post(edit_url, data=form_data, allow_redirects=False)
            
            # Check if redirect happened (successful form submission)
            if response.status_code in [302, 303]:
                # Check database to verify status change
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM invoices WHERE id = ?", (invoice_id,))
                new_status = cursor.fetchone()[0]
                conn.close()
                
                # Revert the change for future tests
                form_data['status'] = original_status
                self.session.post(edit_url, data=form_data)
                
                self.test_results["status_transitions"] = {
                    "status": "PASS" if new_status == 'makstud' else "FAIL",
                    "details": {
                        "invoice_id": invoice_id,
                        "original_status": original_status,
                        "changed_to": new_status,
                        "reverted": True
                    }
                }
                
                print(f"✓ Status Transitions: {'PASS' if new_status == 'makstud' else 'FAIL'}")
                print(f"  Invoice {invoice_number}: {original_status} → {new_status} → {original_status}")
                
            else:
                self.test_results["status_transitions"] = {
                    "status": "FAIL",
                    "details": f"Form submission failed with status {response.status_code}"
                }
                print(f"✗ Status Transitions: FAIL - HTTP {response.status_code}")
                
        except Exception as e:
            self.test_results["status_transitions"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Status Transitions: ERROR - {e}")
    
    def test_dashboard_calculations(self):
        """Test that dashboard financial calculations are correct"""
        print("Testing Dashboard Calculations...")
        try:
            # Get data from database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'maksmata'")
            db_unpaid_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'maksmata'")
            db_unpaid_total = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'makstud'")
            db_paid_total = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM clients")
            db_client_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM invoices")
            db_invoice_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Get dashboard page
            response = self.session.get(f"{BASE_URL}/")
            content = response.text
            
            # Extract values from dashboard
            unpaid_match = re.search(r'Maksmata arved.*?<div class="h4 fw-bold mb-0">(\d+)</div>', content, re.DOTALL)
            unpaid_total_match = re.search(r'<small class="text-danger">([0-9.]+)€</small>', content)
            
            client_count_match = re.search(r'<div class="h5 mb-1">(\d+)</div>.*?Kokku kliente', content, re.DOTALL)
            invoice_count_match = re.search(r'<div class="h5 mb-1">(\d+)</div>.*?Kokku arveid', content, re.DOTALL)
            
            dashboard_unpaid_count = int(unpaid_match.group(1)) if unpaid_match else 0
            dashboard_unpaid_total = float(unpaid_total_match.group(1)) if unpaid_total_match else 0
            dashboard_client_count = int(client_count_match.group(1)) if client_count_match else 0
            dashboard_invoice_count = int(invoice_count_match.group(1)) if invoice_count_match else 0
            
            # Compare values
            calculations_correct = (
                dashboard_unpaid_count == db_unpaid_count and
                abs(dashboard_unpaid_total - float(db_unpaid_total)) < 0.01 and
                dashboard_client_count == db_client_count and
                dashboard_invoice_count == db_invoice_count
            )
            
            self.test_results["dashboard_calculations"] = {
                "status": "PASS" if calculations_correct else "FAIL",
                "details": {
                    "database": {
                        "unpaid_count": db_unpaid_count,
                        "unpaid_total": float(db_unpaid_total),
                        "client_count": db_client_count,
                        "invoice_count": db_invoice_count
                    },
                    "dashboard": {
                        "unpaid_count": dashboard_unpaid_count,
                        "unpaid_total": dashboard_unpaid_total,
                        "client_count": dashboard_client_count,
                        "invoice_count": dashboard_invoice_count
                    }
                }
            }
            
            print(f"✓ Dashboard Calculations: {'PASS' if calculations_correct else 'FAIL'}")
            if not calculations_correct:
                print(f"  Unpaid count: DB={db_unpaid_count}, Dashboard={dashboard_unpaid_count}")
                print(f"  Unpaid total: DB={db_unpaid_total}€, Dashboard={dashboard_unpaid_total}€")
                print(f"  Client count: DB={db_client_count}, Dashboard={dashboard_client_count}")
                print(f"  Invoice count: DB={db_invoice_count}, Dashboard={dashboard_invoice_count}")
                
        except Exception as e:
            self.test_results["dashboard_calculations"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Dashboard Calculations: ERROR - {e}")
    
    def test_invoice_listing_consistency(self):
        """Test that invoice listing shows correct data and status badges"""
        print("Testing Invoice Listing Consistency...")
        try:
            # Get invoice data from database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.number, i.status, i.total, c.name 
                FROM invoices i 
                JOIN clients c ON i.client_id = c.id 
                ORDER BY i.id DESC 
                LIMIT 5
            """)
            db_invoices = cursor.fetchall()
            conn.close()
            
            # Get invoice listing page
            response = self.session.get(f"{BASE_URL}/invoices")
            content = response.text
            
            # Check that each invoice appears correctly
            invoices_found = 0
            for invoice_id, number, status, total, client_name in db_invoices:
                if (number in content and 
                    client_name in content and 
                    status in content and 
                    f"{total:.2f}€".replace('.', ',') in content or f"{total:.2f}€" in content):
                    invoices_found += 1
            
            # Check status badges
            status_badges_correct = ('maksmata' in content or 'makstud' in content)
            
            self.test_results["invoice_listing"] = {
                "status": "PASS" if invoices_found >= len(db_invoices) * 0.8 and status_badges_correct else "FAIL",
                "details": {
                    "total_invoices": len(db_invoices),
                    "invoices_found": invoices_found,
                    "status_badges_present": status_badges_correct
                }
            }
            
            print(f"✓ Invoice Listing: {'PASS' if invoices_found >= len(db_invoices) * 0.8 and status_badges_correct else 'FAIL'}")
            print(f"  Found {invoices_found}/{len(db_invoices)} invoices correctly displayed")
            
        except Exception as e:
            self.test_results["invoice_listing"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ Invoice Listing: ERROR - {e}")
    
    def test_system_responsiveness(self):
        """Test that the system responds quickly to requests"""
        print("Testing System Responsiveness...")
        try:
            import time
            
            # Test multiple pages
            pages = [
                ('/', 'Dashboard'),
                ('/invoices', 'Invoice List'),
                ('/clients', 'Client List'),
                ('/settings', 'Settings')
            ]
            
            response_times = {}
            all_fast = True
            
            for url, name in pages:
                start_time = time.time()
                response = self.session.get(f"{BASE_URL}{url}")
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times[name] = response_time
                
                if response_time > 2.0:  # Consider slow if > 2 seconds
                    all_fast = False
            
            self.test_results["responsiveness"] = {
                "status": "PASS" if all_fast else "FAIL",
                "details": response_times
            }
            
            print(f"✓ System Responsiveness: {'PASS' if all_fast else 'FAIL'}")
            for page, time_taken in response_times.items():
                print(f"  {page}: {time_taken:.3f}s")
                
        except Exception as e:
            self.test_results["responsiveness"] = {"status": "ERROR", "details": str(e)}
            print(f"✗ System Responsiveness: ERROR - {e}")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*70)
        print("BILLIPOCKET COMPREHENSIVE FUNCTIONAL TEST REPORT")
        print("="*70)
        print(f"Test executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        failed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'FAIL')
        error_tests = sum(1 for result in self.test_results.values() if result['status'] == 'ERROR')
        skipped_tests = sum(1 for result in self.test_results.values() if result['status'] == 'SKIP')
        
        print(f"SUMMARY:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {failed_tests}")
        print(f"  Errors: {error_tests}")
        print(f"  Skipped: {skipped_tests}")
        print(f"  Success Rate: {(passed_tests/(total_tests-skipped_tests)*100):.1f}%")
        print()
        
        print("DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status_symbol = {
                'PASS': '✓',
                'FAIL': '✗',
                'ERROR': '⚠',
                'SKIP': '○'
            }.get(result['status'], '?')
            
            print(f"  {status_symbol} {test_name.upper()}: {result['status']}")
            
            if result['status'] == 'PASS':
                # Show some key metrics for passed tests
                if test_name == 'database_status_system':
                    details = result['details']
                    print(f"    Status counts: {details['status_counts']}")
                elif test_name == 'dashboard_calculations':
                    details = result['details']
                    print(f"    Unpaid: {details['database']['unpaid_count']} invoices, {details['database']['unpaid_total']}€")
            elif result['status'] != 'PASS':
                print(f"    Details: {result.get('details', 'No details')}")
        
        print("\n" + "="*70)
        print("SYSTEM STATUS: " + ("HEALTHY" if passed_tests >= total_tests - skipped_tests else "NEEDS ATTENTION"))
        print("="*70)
        
        return passed_tests >= total_tests - skipped_tests
    
    def run_all_tests(self):
        """Run all functional workflow tests"""
        print("Starting BilliPocket comprehensive functional tests...\n")
        
        self.test_database_status_system()
        self.test_dashboard_calculations()
        self.test_invoice_listing_consistency()
        self.test_invoice_status_transitions()
        self.test_system_responsiveness()
        
        return self.generate_report()

if __name__ == "__main__":
    tester = WorkflowTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)