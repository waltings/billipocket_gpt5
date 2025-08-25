#!/usr/bin/env python3
"""
Test script to reproduce the VAT rate reset bug.
This simulates the exact user workflow:
1. Load invoice edit form (should show current VAT rate)
2. Change VAT rate to 0%
3. Submit form (should save with 0%)
4. Verify result (currently fails - resets to 24%)
"""

import requests
from bs4 import BeautifulSoup
import re

def test_vat_rate_bug():
    """Test the VAT rate bug workflow."""
    session = requests.Session()
    base_url = "http://127.0.0.1:5010"
    
    print("🚀 Starting VAT rate bug test...")
    
    # Step 1: Load invoice edit form
    print("\n📋 Step 1: Loading invoice edit form...")
    edit_url = f"{base_url}/invoices/12/edit"
    response = session.get(edit_url)
    
    if response.status_code != 200:
        print(f"❌ Failed to load edit form: {response.status_code}")
        return False
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract form data
    csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
    current_vat_rate_id = soup.find('input', {'id': 'vat_rate_id'})['value']
    
    print(f"   Current VAT rate ID: {current_vat_rate_id}")
    print(f"   CSRF token: {csrf_token[:20]}...")
    
    # Get current VAT rate display
    vat_display = soup.find(id='vatRateLabel')
    if vat_display:
        current_display = vat_display.get_text()
        print(f"   Current VAT display: {current_display}")
    
    # Step 2: Find the 0% VAT rate ID
    print("\n🔍 Step 2: Finding 0% VAT rate option...")
    vat_options = soup.find_all('a', class_='vat-rate-option')
    zero_percent_id = None
    
    for option in vat_options:
        if '(0%)' in option.get_text():
            zero_percent_id = option.get('data-rate-id')
            print(f"   Found 0% VAT rate with ID: {zero_percent_id}")
            break
    
    if not zero_percent_id:
        print("❌ Could not find 0% VAT rate option!")
        return False
    
    # Step 3: Extract all form data for submission
    print("\n📝 Step 3: Preparing form submission with 0% VAT rate...")
    
    # Get all form fields
    form_data = {}
    form_data['csrf_token'] = csrf_token
    form_data['vat_rate_id'] = zero_percent_id  # Change to 0%
    
    # Extract other form fields with proper handling
    field_mappings = {
        'number': ('input', 'value'),
        'client_id': ('input', 'value'),
        'date': ('input', 'value'),
        'due_date': ('input', 'value'),
        'status': ('input', 'value'),
        'payment_terms': ('input', 'value'),
        'client_extra_info': ('textarea', 'text'),
        'note': ('textarea', 'text'),
        'announcements': ('textarea', 'text'),
        'pdf_template': ('input', 'value')
    }
    
    for field, (tag_type, attr_type) in field_mappings.items():
        if tag_type == 'input':
            # Handle input fields
            input_field = soup.find('input', {'name': field})
            if input_field:
                form_data[field] = input_field.get('value', '')
            else:
                # Handle select fields
                select_field = soup.find('select', {'name': field})
                if select_field:
                    selected_option = select_field.find('option', selected=True)
                    if selected_option:
                        form_data[field] = selected_option.get('value', '')
                    else:
                        # If no selected option, get the first option value
                        first_option = select_field.find('option')
                        if first_option:
                            form_data[field] = first_option.get('value', '')
        elif tag_type == 'textarea':
            textarea_field = soup.find('textarea', {'name': field})
            if textarea_field:
                form_data[field] = textarea_field.get_text() if attr_type == 'text' else textarea_field.get('value', '')
    
    # Handle invoice lines
    line_index = 0
    while True:
        line_prefix = f"lines-{line_index}"
        
        # Check if this line exists
        desc_field = soup.find('input', {'name': f'{line_prefix}-description'})
        if not desc_field:
            break
            
        # Extract line data
        qty_field = soup.find('input', {'name': f'{line_prefix}-qty'})
        price_field = soup.find('input', {'name': f'{line_prefix}-unit_price'})
        total_field = soup.find('input', {'name': f'{line_prefix}-line_total'})
        id_field = soup.find('input', {'name': f'{line_prefix}-id'})
        
        form_data[f'{line_prefix}-description'] = desc_field.get('value', '')
        form_data[f'{line_prefix}-qty'] = qty_field.get('value', '') if qty_field else ''
        form_data[f'{line_prefix}-unit_price'] = price_field.get('value', '') if price_field else ''
        form_data[f'{line_prefix}-line_total'] = total_field.get('value', '') if total_field else ''
        form_data[f'{line_prefix}-id'] = id_field.get('value', '') if id_field else ''
        
        line_index += 1
    
    print(f"   Found {line_index} invoice lines")
    print(f"   VAT rate changed from {current_vat_rate_id} to {zero_percent_id} (0%)")
    
    # Debug: Print key form data
    print(f"   Form data keys: {list(form_data.keys())}")
    print(f"   Status field: '{form_data.get('status', 'NOT_FOUND')}'")
    print(f"   Client ID: '{form_data.get('client_id', 'NOT_FOUND')}'")
    
    # Step 4: Submit the form
    print("\n📤 Step 4: Submitting form with 0% VAT rate...")
    response = session.post(edit_url, data=form_data)
    
    if response.status_code == 302:
        print("   Form submitted successfully (redirect received)")
        redirect_url = response.headers.get('Location')
        print(f"   Redirect URL: {redirect_url}")
    else:
        print(f"   Unexpected response: {response.status_code}")
        print(f"   Response text: {response.text[:500]}...")
        return False
    
    # Step 5: Verify the result by checking the invoice detail
    print("\n🔍 Step 5: Verifying VAT rate was saved...")
    
    if redirect_url:
        # Follow redirect to view invoice
        final_response = session.get(f"{base_url}{redirect_url}")
        if final_response.status_code == 200:
            final_soup = BeautifulSoup(final_response.text, 'html.parser')
            
            # Look for VAT rate in the invoice display
            vat_elements = final_soup.find_all(string=re.compile(r'KM.*\d+%'))
            for vat_text in vat_elements:
                print(f"   Found VAT text: {vat_text.strip()}")
                if '0%' in vat_text:
                    print("✅ SUCCESS: VAT rate correctly saved as 0%!")
                    return True
                elif '24%' in vat_text:
                    print("❌ BUG CONFIRMED: VAT rate was reset to 24%!")
                    return False
    
    # Step 6: Double-check by re-editing
    print("\n🔄 Step 6: Double-checking by loading edit form again...")
    recheck_response = session.get(edit_url)
    if recheck_response.status_code == 200:
        recheck_soup = BeautifulSoup(recheck_response.text, 'html.parser')
        final_vat_rate_id = recheck_soup.find('input', {'id': 'vat_rate_id'})['value']
        
        print(f"   VAT rate ID in edit form: {final_vat_rate_id}")
        
        if final_vat_rate_id == zero_percent_id:
            print("✅ SUCCESS: VAT rate correctly saved as 0%!")
            return True
        elif final_vat_rate_id == current_vat_rate_id:
            print("❌ BUG CONFIRMED: VAT rate was reset to original value!")
            return False
        else:
            print(f"❓ UNEXPECTED: VAT rate is now {final_vat_rate_id}")
            return False
    
    print("❌ Could not verify final state")
    return False

if __name__ == "__main__":
    success = test_vat_rate_bug()
    print(f"\n🏁 Test result: {'SUCCESS' if success else 'FAILURE'}")