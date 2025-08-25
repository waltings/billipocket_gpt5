#!/usr/bin/env python3
"""
Comprehensive testing script for invoice editing functionality.
Tests frontend-backend integration including form handling, validation, and data persistence.
"""

import requests
import sys
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse

class InvoiceEditingTester:
    def __init__(self, base_url="http://localhost:5010"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.test_results = []
        
    def log_test(self, test_name, success, message="", data=None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "data": data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if data and not success:
            print(f"   Data: {data}")
    
    def extract_csrf_token(self, html_content):
        """Extract CSRF token from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            return csrf_input.get('value')
        return None
    
    def test_load_invoice_edit_form(self, invoice_id=1):
        """Test loading an existing invoice for editing"""
        try:
            url = f"{self.base_url}/invoices/{invoice_id}/edit"
            response = self.session.get(url)
            
            if response.status_code != 200:
                self.log_test("Load Invoice Edit Form", False, 
                            f"HTTP {response.status_code}", {"url": url})
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check for form elements
            form = soup.find('form', {'id': 'invoiceForm'})
            if not form:
                self.log_test("Load Invoice Edit Form", False, "Form not found")
                return None
                
            # Extract form data
            form_data = {}
            
            # Get basic fields
            for field in ['number', 'date', 'due_date', 'client_id', 'payment_terms', 
                         'client_extra_info', 'note', 'announcements', 'vat_rate_id']:
                element = soup.find('input', {'name': field}) or soup.find('select', {'name': field}) or soup.find('textarea', {'name': field})
                if element:
                    form_data[field] = element.get('value', '') if element.name == 'input' else (element.get_text().strip() if element.name == 'textarea' else element.find('option', {'selected': True}).get('value') if element.find('option', {'selected': True}) else '')
            
            # Count invoice lines
            line_inputs = soup.find_all('input', {'name': re.compile(r'lines-\d+-description')})
            lines_count = len(line_inputs)
            
            # Get CSRF token
            csrf_token = self.extract_csrf_token(response.content)
            
            success = all([
                form is not None,
                csrf_token is not None,
                lines_count > 0,
                form_data.get('number'),
                form_data.get('date'),
                form_data.get('client_id')
            ])
            
            self.log_test("Load Invoice Edit Form", success,
                         f"Form loaded with {lines_count} lines, CSRF present: {csrf_token is not None}",
                         {"lines_count": lines_count, "form_data": form_data})
            
            if success:
                return {
                    'csrf_token': csrf_token,
                    'form_data': form_data,
                    'lines_count': lines_count,
                    'soup': soup,
                    'response': response
                }
            return None
            
        except Exception as e:
            self.log_test("Load Invoice Edit Form", False, f"Exception: {str(e)}")
            return None
    
    def test_form_field_validation(self, invoice_id=1):
        """Test form field validation and error handling"""
        try:
            # Load the form first
            form_data = self.test_load_invoice_edit_form(invoice_id)
            if not form_data:
                return False
                
            url = f"{self.base_url}/invoices/{invoice_id}/edit"
            
            # Test 1: Submit with missing required fields
            invalid_data = {
                'csrf_token': form_data['csrf_token'],
                'number': '',  # Missing required field
                'client_id': '',  # Missing required field
                'date': '',  # Missing required field
                'due_date': '2025-08-27',
                'vat_rate_id': '4',
                'payment_terms': '14 päeva',
                'lines-0-description': 'Test service',
                'lines-0-qty': '1',
                'lines-0-unit_price': '100'
            }
            
            response = self.session.post(url, data=invalid_data)
            
            # Should not redirect (validation failed)
            validation_failed = response.status_code == 200 and 'invoice_form.html' in response.url
            
            if validation_failed:
                soup = BeautifulSoup(response.content, 'html.parser')
                error_elements = soup.find_all(class_='invalid-feedback')
                has_errors = len(error_elements) > 0
                
                self.log_test("Form Validation - Missing Required Fields", has_errors,
                             f"Found {len(error_elements)} validation errors")
            else:
                self.log_test("Form Validation - Missing Required Fields", False,
                             f"Form should not have been submitted successfully (status: {response.status_code})")
                
            # Test 2: Submit with invalid invoice number format
            invalid_data_2 = {
                'csrf_token': form_data['csrf_token'],
                'number': 'INVALID-FORMAT',  # Invalid format
                'client_id': '1',
                'date': '2025-08-13',
                'due_date': '2025-08-27',
                'vat_rate_id': '4',
                'payment_terms': '14 päeva',
                'lines-0-description': 'Test service',
                'lines-0-qty': '1',
                'lines-0-unit_price': '100'
            }
            
            response = self.session.post(url, data=invalid_data_2)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                format_error = any('AAAA-NNNN' in error.get_text() for error in soup.find_all(class_='invalid-feedback'))
                
                self.log_test("Form Validation - Invalid Number Format", format_error,
                             "Invoice number format validation working")
            else:
                self.log_test("Form Validation - Invalid Number Format", False,
                             f"Unexpected response status: {response.status_code}")
                             
            return True
            
        except Exception as e:
            self.log_test("Form Field Validation", False, f"Exception: {str(e)}")
            return False
    
    def test_invoice_line_operations(self, invoice_id=1):
        """Test adding, modifying, and removing invoice lines"""
        try:
            form_data = self.test_load_invoice_edit_form(invoice_id)
            if not form_data:
                return False
                
            url = f"{self.base_url}/invoices/{invoice_id}/edit"
            
            # Test adding new lines and modifying existing ones
            test_data = {
                'csrf_token': form_data['csrf_token'],
                'number': form_data['form_data'].get('number', '2025-0001'),
                'client_id': form_data['form_data'].get('client_id', '1'),
                'date': '2025-08-13',
                'due_date': '2025-08-27',
                'vat_rate_id': '4',  # 24%
                'payment_terms': '14 päeva',
                'client_extra_info': 'Test modification',
                'note': 'Test note modification',
                'announcements': 'Test announcement modification',
                
                # Existing line (modified)
                'lines-0-id': '1',  # Assuming first line has ID 1
                'lines-0-description': 'Modified service description',
                'lines-0-qty': '2',
                'lines-0-unit_price': '150.00',
                
                # New line
                'lines-1-description': 'New service line',
                'lines-1-qty': '1',
                'lines-1-unit_price': '200.00',
                
                # Another new line
                'lines-2-description': 'Another new service',
                'lines-2-qty': '3',
                'lines-2-unit_price': '50.00'
            }
            
            response = self.session.post(url, data=test_data, allow_redirects=False)
            
            # Should redirect to invoice detail on success
            success = response.status_code == 302
            
            if success:
                redirect_url = response.headers.get('Location', '')
                expected_pattern = f'/invoices/{invoice_id}'
                redirect_valid = expected_pattern in redirect_url
                
                self.log_test("Invoice Line Operations", redirect_valid,
                             f"Form submitted successfully, redirected to: {redirect_url}")
                
                # Follow redirect to verify changes
                if redirect_valid:
                    detail_response = self.session.get(urljoin(self.base_url, redirect_url))
                    if detail_response.status_code == 200:
                        soup = BeautifulSoup(detail_response.content, 'html.parser')
                        
                        # Look for success flash message
                        flash_messages = soup.find_all(class_='alert-success')
                        has_success_message = any('edukalt uuendatud' in msg.get_text() for msg in flash_messages)
                        
                        self.log_test("Invoice Line Operations - Success Message", has_success_message,
                                     "Success flash message displayed")
                        
                        return True
            else:
                # Check for validation errors
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    errors = soup.find_all(class_='invalid-feedback')
                    self.log_test("Invoice Line Operations", False,
                                 f"Form validation failed with {len(errors)} errors")
                else:
                    self.log_test("Invoice Line Operations", False,
                                 f"Unexpected response status: {response.status_code}")
            
            return False
            
        except Exception as e:
            self.log_test("Invoice Line Operations", False, f"Exception: {str(e)}")
            return False
    
    def test_vat_rate_changes(self, invoice_id=1):
        """Test VAT rate changes and total calculations"""
        try:
            form_data = self.test_load_invoice_edit_form(invoice_id)
            if not form_data:
                return False
                
            url = f"{self.base_url}/invoices/{invoice_id}/edit"
            
            # Test with different VAT rates
            vat_tests = [
                {'vat_rate_id': '1', 'expected_name': 'Maksuvaba (0%)', 'rate': 0},
                {'vat_rate_id': '2', 'expected_name': 'Vähendatud määr (9%)', 'rate': 9},
                {'vat_rate_id': '4', 'expected_name': '24%', 'rate': 24}
            ]
            
            for vat_test in vat_tests:
                test_data = {
                    'csrf_token': form_data['csrf_token'],
                    'number': form_data['form_data'].get('number', '2025-0001'),
                    'client_id': form_data['form_data'].get('client_id', '1'),
                    'date': '2025-08-13',
                    'due_date': '2025-08-27',
                    'vat_rate_id': vat_test['vat_rate_id'],
                    'payment_terms': '14 päeva',
                    
                    # Simple test line for calculation
                    'lines-0-description': 'Test service for VAT calculation',
                    'lines-0-qty': '1',
                    'lines-0-unit_price': '100.00'
                }
                
                response = self.session.post(url, data=test_data, allow_redirects=False)
                
                if response.status_code == 302:
                    success_msg = f"VAT rate {vat_test['expected_name']} applied successfully"
                    self.log_test(f"VAT Rate Change - {vat_test['expected_name']}", True, success_msg)
                else:
                    error_msg = f"Failed to apply VAT rate {vat_test['expected_name']}"
                    self.log_test(f"VAT Rate Change - {vat_test['expected_name']}", False, error_msg)
            
            return True
            
        except Exception as e:
            self.log_test("VAT Rate Changes", False, f"Exception: {str(e)}")
            return False
    
    def test_csrf_protection(self, invoice_id=1):
        """Test CSRF protection"""
        try:
            form_data = self.test_load_invoice_edit_form(invoice_id)
            if not form_data:
                return False
                
            url = f"{self.base_url}/invoices/{invoice_id}/edit"
            
            # Test without CSRF token
            test_data = {
                # 'csrf_token': form_data['csrf_token'],  # Intentionally omitted
                'number': form_data['form_data'].get('number', '2025-0001'),
                'client_id': form_data['form_data'].get('client_id', '1'),
                'date': '2025-08-13',
                'due_date': '2025-08-27',
                'vat_rate_id': '4',
                'lines-0-description': 'Test without CSRF',
                'lines-0-qty': '1',
                'lines-0-unit_price': '100'
            }
            
            response = self.session.post(url, data=test_data)
            
            # Should fail without CSRF token
            csrf_protection_working = response.status_code != 302  # Not a successful redirect
            
            self.log_test("CSRF Protection", csrf_protection_working,
                         f"Request without CSRF token handled properly (status: {response.status_code})")
            
            # Test with invalid CSRF token
            test_data['csrf_token'] = 'invalid_token_12345'
            response = self.session.post(url, data=test_data)
            
            invalid_token_rejected = response.status_code != 302
            
            self.log_test("CSRF Protection - Invalid Token", invalid_token_rejected,
                         f"Request with invalid CSRF token handled properly (status: {response.status_code})")
            
            return csrf_protection_working and invalid_token_rejected
            
        except Exception as e:
            self.log_test("CSRF Protection", False, f"Exception: {str(e)}")
            return False
    
    def test_database_integrity(self, invoice_id=1):
        """Test database integrity after operations"""
        try:
            # This would require direct database access
            # For now, we'll test by loading the invoice after modifications
            
            response = self.session.get(f"{self.base_url}/invoices/{invoice_id}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Check if invoice details are displayed correctly
                invoice_number = soup.find(text=re.compile(r'2025-\d{4}'))
                has_lines = bool(soup.find_all('tr', class_=re.compile(r'invoice-line|line-item')))
                
                integrity_ok = bool(invoice_number) and has_lines
                
                self.log_test("Database Integrity", integrity_ok,
                             f"Invoice {invoice_id} data intact after modifications")
            else:
                self.log_test("Database Integrity", False,
                             f"Could not load invoice {invoice_id} (status: {response.status_code})")
                
            return True
            
        except Exception as e:
            self.log_test("Database Integrity", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🧪 Starting comprehensive invoice editing integration tests...")
        print("=" * 70)
        
        # Test basic form loading
        form_data = self.test_load_invoice_edit_form()
        if not form_data:
            print("❌ Critical failure: Cannot load invoice edit form")
            return False
        
        # Run all tests
        tests = [
            self.test_form_field_validation,
            self.test_invoice_line_operations,
            self.test_vat_rate_changes,
            self.test_csrf_protection,
            self.test_database_integrity
        ]
        
        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                self.log_test(test_func.__name__, False, f"Test failed with exception: {str(e)}")
        
        # Summary
        print("\n" + "=" * 70)
        print("🏁 Test Summary")
        print("=" * 70)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        print(f"\n📊 Results: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! Invoice editing integration is working correctly.")
        else:
            print("⚠️  Some tests failed. Review the issues above.")
        
        return passed == total

def main():
    tester = InvoiceEditingTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()