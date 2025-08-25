#!/usr/bin/env python3
"""
Manual testing guide for invoice editing functionality.
Provides step-by-step instructions and validation checks.
"""

import requests
from bs4 import BeautifulSoup
import json
import re

class ManualTestingGuide:
    def __init__(self, base_url="http://localhost:5010"):
        self.base_url = base_url
        
    def analyze_form_structure(self, invoice_id=1):
        """Analyze the form structure and JavaScript integration"""
        print("🔍 ANALYZING INVOICE EDIT FORM STRUCTURE")
        print("=" * 60)
        
        try:
            response = requests.get(f"{self.base_url}/invoices/{invoice_id}/edit")
            if response.status_code != 200:
                print(f"❌ Cannot access form: HTTP {response.status_code}")
                return
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Form Security Analysis
            print("🔒 SECURITY ANALYSIS")
            csrf_token = soup.find('input', {'name': 'csrf_token'})
            print(f"   CSRF Protection: {'✅ Present' if csrf_token else '❌ Missing'}")
            
            form = soup.find('form', {'id': 'invoiceForm'})
            method = form.get('method', '').upper() if form else 'UNKNOWN'
            print(f"   Form Method: {method} {'✅' if method == 'POST' else '❌'}")
            
            # 2. Field Analysis
            print("\\n📋 FORM FIELDS ANALYSIS")
            
            required_fields = [
                'number', 'client_id', 'date', 'due_date', 'vat_rate_id'
            ]
            
            for field in required_fields:
                element = soup.find('input', {'name': field}) or soup.find('select', {'name': field})
                if element:
                    required = 'required' in element.attrs
                    validation_class = 'is-invalid' in element.get('class', [])
                    print(f"   {field:15}: ✅ Present {'(Required)' if required else '(Optional)'}")
                else:
                    print(f"   {field:15}: ❌ Missing")
            
            # 3. Invoice Lines Analysis
            print("\\n📝 INVOICE LINES ANALYSIS")
            
            line_descriptions = soup.find_all('input', {'name': re.compile(r'lines-\\d+-description')})
            line_qtys = soup.find_all('input', {'name': re.compile(r'lines-\\d+-qty')})
            line_prices = soup.find_all('input', {'name': re.compile(r'lines-\\d+-unit_price')})
            
            print(f"   Description fields: {len(line_descriptions)}")
            print(f"   Quantity fields: {len(line_qtys)}")
            print(f"   Price fields: {len(line_prices)}")
            print(f"   Lines consistency: {'✅' if len(line_descriptions) == len(line_qtys) == len(line_prices) else '❌'}")
            
            # 4. JavaScript Integration Analysis
            print("\\n⚡ JAVASCRIPT INTEGRATION ANALYSIS")
            
            js_functions = [
                'addInvoiceLine', 'removeInvoiceLine', 'updateTotals', 
                'addLineEventListeners', 'submitAndSend'
            ]
            
            script_content = ''
            for script in soup.find_all('script'):
                if script.string:
                    script_content += script.string
                    
            for func in js_functions:
                present = func in script_content
                print(f"   {func:20}: {'✅ Present' if present else '❌ Missing'}")
            
            # 5. VAT Rate Integration
            print("\\n💰 VAT RATE INTEGRATION")
            
            vat_dropdown = soup.find('div', {'id': 'vatRateDropdown'}) or soup.find('ul', {'id': 'vatRateDropdown'})
            vat_options = soup.find_all('a', {'class': 'vat-rate-option'}) if vat_dropdown else []
            
            print(f"   VAT Rate Selector: {'✅ Present' if vat_dropdown else '❌ Missing'}")
            print(f"   VAT Options: {len(vat_options)} available")
            
            vat_mapping = 'vatRateMap' in script_content
            print(f"   JS VAT Mapping: {'✅ Present' if vat_mapping else '❌ Missing'}")
            
            # 6. Total Calculation Elements
            print("\\n🧮 TOTAL CALCULATION ELEMENTS")
            
            calc_elements = ['subtotal', 'vat-amount', 'total-amount', 'vat-rate-display']
            
            for element_id in calc_elements:
                element = soup.find(id=element_id)
                print(f"   {element_id:15}: {'✅ Present' if element else '❌ Missing'}")
            
            print("\\n" + "=" * 60)
            print("✅ FORM STRUCTURE ANALYSIS COMPLETE")
            
        except Exception as e:
            print(f"❌ Analysis failed: {str(e)}")
    
    def generate_test_scenarios(self):
        """Generate comprehensive test scenarios for manual testing"""
        print("\\n\\n📋 MANUAL TESTING SCENARIOS")
        print("=" * 60)
        
        scenarios = [
            {
                "name": "Basic Form Loading",
                "steps": [
                    "1. Navigate to /invoices/1/edit",
                    "2. Verify form loads within 3 seconds",
                    "3. Check all fields are populated with existing data",
                    "4. Verify invoice lines are displayed correctly",
                    "5. Confirm VAT rate selector shows current rate"
                ],
                "expected": "Form loads completely with all existing invoice data"
            },
            {
                "name": "Header Field Modification",
                "steps": [
                    "1. Change invoice date to tomorrow",
                    "2. Change client to different client",
                    "3. Modify payment terms",
                    "4. Add text to 'Client extra info' field",
                    "5. Add text to 'Note' field",
                    "6. Add text to 'Announcements' field"
                ],
                "expected": "All field changes are preserved during form interactions"
            },
            {
                "name": "Invoice Line Operations",
                "steps": [
                    "1. Click 'Lisa rida' (Add line) button",
                    "2. Fill new line: Description, Quantity=2, Unit Price=50.00",
                    "3. Verify line total shows 100.00€",
                    "4. Modify existing line quantity to 3",
                    "5. Verify line total recalculates",
                    "6. Delete a line using trash button",
                    "7. Confirm line is removed from display"
                ],
                "expected": "Lines can be added, modified, and removed with real-time calculations"
            },
            {
                "name": "VAT Rate Changes",
                "steps": [
                    "1. Click VAT rate selector button",
                    "2. Select '0%' VAT rate",
                    "3. Verify button text changes to 'KM (0%)'",
                    "4. Check that VAT amount becomes 0.00€",
                    "5. Change to 9% VAT rate",
                    "6. Verify calculations update immediately",
                    "7. Change back to 24% VAT rate"
                ],
                "expected": "VAT rate changes immediately update all calculations and display"
            },
            {
                "name": "Real-time Calculations",
                "steps": [
                    "1. Clear all existing lines",
                    "2. Add line: Qty=5, Price=20.00",
                    "3. Verify subtotal shows 100.00€",
                    "4. With 24% VAT, verify total shows 124.00€",
                    "5. Change quantity to 10",
                    "6. Verify subtotal updates to 200.00€",
                    "7. Verify total updates to 248.00€"
                ],
                "expected": "All totals calculate and update immediately without page refresh"
            },
            {
                "name": "Form Validation",
                "steps": [
                    "1. Clear invoice number field",
                    "2. Try to submit form",
                    "3. Verify validation error appears",
                    "4. Clear client selection",
                    "5. Try to submit form",
                    "6. Verify multiple validation errors",
                    "7. Remove all invoice lines",
                    "8. Try to submit form"
                ],
                "expected": "Validation prevents submission and shows clear error messages"
            },
            {
                "name": "Successful Form Submission",
                "steps": [
                    "1. Ensure all required fields are filled",
                    "2. Ensure at least one complete invoice line exists",
                    "3. Click 'Uuenda arvet' (Update Invoice) button",
                    "4. Verify redirect to invoice detail page",
                    "5. Check for success flash message in Estonian",
                    "6. Verify all changes are reflected on detail page"
                ],
                "expected": "Form submits successfully with redirect and confirmation message"
            },
            {
                "name": "Error Handling",
                "steps": [
                    "1. Enter duplicate invoice number (if exists)",
                    "2. Try to submit form",
                    "3. Verify duplicate number error",
                    "4. Enter invalid invoice number format 'ABC123'",
                    "5. Try to submit form",
                    "6. Verify format validation error",
                    "7. Test with negative quantities or prices"
                ],
                "expected": "All validation errors are caught and displayed clearly in Estonian"
            },
            {
                "name": "Browser Compatibility",
                "steps": [
                    "1. Test in Chrome/Safari",
                    "2. Test JavaScript functionality",
                    "3. Test responsive design on mobile",
                    "4. Verify form submission works",
                    "5. Check for console errors"
                ],
                "expected": "Functionality works consistently across browsers"
            },
            {
                "name": "Data Persistence",
                "steps": [
                    "1. Make complex changes (multiple lines, different VAT)",
                    "2. Submit form successfully",
                    "3. Navigate back to edit form",
                    "4. Verify all changes persisted correctly",
                    "5. Check database integrity via other invoice"
                ],
                "expected": "All changes are saved correctly and persist between sessions"
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\\n🧪 TEST SCENARIO {i}: {scenario['name']}")
            print("-" * 50)
            print("STEPS:")
            for step in scenario['steps']:
                print(f"  {step}")
            print(f"\\nEXPECTED RESULT: {scenario['expected']}")
        
        print("\\n" + "=" * 60)
        print("📝 TESTING CHECKLIST")
        print("=" * 60)
        
        checklist_items = [
            "[ ] Form loads quickly and completely",
            "[ ] All existing data populates correctly", 
            "[ ] Invoice lines display with proper data",
            "[ ] JavaScript functions work (add/remove lines)",
            "[ ] Real-time calculations work accurately",
            "[ ] VAT rate selector functions properly",
            "[ ] Form validation prevents invalid submissions",
            "[ ] Success messages appear in Estonian",
            "[ ] Error messages appear in Estonian",
            "[ ] Redirects work after successful submission",
            "[ ] CSRF protection is active",
            "[ ] Mobile responsive design works",
            "[ ] Data persists correctly in database",
            "[ ] No JavaScript console errors",
            "[ ] Accessibility features present (labels, etc.)"
        ]
        
        for item in checklist_items:
            print(f"  {item}")
        
        print("\\n✅ Complete all checklist items to verify full integration")

def main():
    guide = ManualTestingGuide()
    guide.analyze_form_structure()
    guide.generate_test_scenarios()

if __name__ == "__main__":
    main()