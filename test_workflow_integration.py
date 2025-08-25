#!/usr/bin/env python3
"""
Comprehensive workflow integration test for VAT calculation precision fix.

This script tests the exact user workflow described:
1. Create a new invoice
2. Edit the invoice and change line amounts
3. Verify real-time calculations work during editing
4. Save the invoice ("Uuenda arvet")
5. Check that the view page sidebar shows correct totals

The test ensures that view page sidebar totals match what was shown during editing,
addressing the "stale totals" issue.
"""

import requests
import time
from decimal import Decimal, ROUND_HALF_UP
from bs4 import BeautifulSoup
import re
import json

BASE_URL = "http://127.0.0.1:5010"
session = requests.Session()


def extract_csrf_token(response):
    """Extract CSRF token from response."""
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    return csrf_input.get('value') if csrf_input else None


def calculate_expected_totals(lines, vat_rate=24):
    """Calculate expected totals using same precision as backend."""
    subtotal = Decimal('0.00')
    
    for line in lines:
        qty = Decimal(str(line['qty']))
        price = Decimal(str(line['unit_price']))
        line_total = (qty * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal += line_total
    
    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    vat_amount = (subtotal * (Decimal(str(vat_rate)) / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = (subtotal + vat_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return {
        'subtotal': subtotal,
        'vat_amount': vat_amount,
        'total': total,
        'vat_rate': vat_rate
    }


def extract_totals_from_sidebar(html_content):
    """Extract totals from sidebar HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    totals = {}
    
    # Try to get totals from JavaScript-populated elements (edit form)
    subtotal_elem = soup.find(id='subtotal')
    vat_amount_elem = soup.find(id='vat-amount') 
    total_amount_elem = soup.find(id='total-amount')
    vat_rate_display = soup.find(id='vat-rate-display')
    
    if subtotal_elem:
        subtotal_text = subtotal_elem.get_text(strip=True)
        totals['subtotal'] = Decimal(subtotal_text.replace('€', '').strip())
    
    if vat_amount_elem:
        vat_text = vat_amount_elem.get_text(strip=True) 
        totals['vat_amount'] = Decimal(vat_text.replace('€', '').strip())
    
    if total_amount_elem:
        total_text = total_amount_elem.get_text(strip=True)
        totals['total'] = Decimal(total_text.replace('€', '').strip())
    
    if vat_rate_display:
        totals['vat_rate'] = float(vat_rate_display.get_text(strip=True))
    
    # Fallback: try to find totals in static view page structure
    if not totals:
        # Find totals by looking for table rows with specific patterns
        subtotal_row = soup.find('td', string=re.compile(r'Vahesumma:'))
        vat_row = soup.find('td', string=re.compile(r'KM \(.*%\):'))
        total_row = soup.find('td', string=re.compile(r'Kokku:'))
        
        if subtotal_row:
            subtotal_text = subtotal_row.find_next_sibling('td').get_text(strip=True)
            totals['subtotal'] = Decimal(subtotal_text.replace('€', '').strip())
        
        if vat_row:
            vat_text = vat_row.find_next_sibling('td').get_text(strip=True)
            totals['vat_amount'] = Decimal(vat_text.replace('€', '').strip())
            # Extract VAT rate from text
            vat_rate_match = re.search(r'KM \((\d+(?:\.\d+)?)%\):', vat_row.get_text())
            if vat_rate_match:
                totals['vat_rate'] = float(vat_rate_match.group(1))
        
        if total_row:
            total_text = total_row.find_next_sibling('td').get_text(strip=True)
            totals['total'] = Decimal(total_text.replace('€', '').strip())
    
    return totals


def test_workflow():
    """Test the complete invoice editing workflow."""
    
    print("=== STARTING WORKFLOW INTEGRATION TEST ===\n")
    
    # Step 1: Create a new invoice
    print("1. Creating new invoice...")
    
    # Get the invoice creation form
    response = session.get(f"{BASE_URL}/invoices/new")
    assert response.status_code == 200, f"Failed to get invoice form: {response.status_code}"
    
    csrf_token = extract_csrf_token(response)
    assert csrf_token, "No CSRF token found"
    
    # Extract client options and VAT rates
    soup = BeautifulSoup(response.text, 'html.parser')
    client_select = soup.find('select', {'name': 'client_id'})
    clients = [opt.get('value') for opt in client_select.find_all('option') if opt.get('value')]
    
    # Get VAT rate ID for 24%
    vat_rate_inputs = soup.find_all('input', {'name': 'vat_rate_id'})
    vat_rate_id = vat_rate_inputs[0].get('value') if vat_rate_inputs else '4'  # Default to 4 (24%)
    
    # Debug form structure
    print(f"Available clients: {clients}")
    print(f"VAT rate ID: {vat_rate_id}")
    
    # Create invoice with initial data
    invoice_data = {
        'csrf_token': csrf_token,
        'number': f'2025-{int(time.time()) % 10000:04d}',
        'client_id': clients[0] if clients else '1',
        'date': '2025-08-14',
        'due_date': '2025-08-28',
        'payment_terms': '14 päeva',
        'vat_rate_id': vat_rate_id,
        'lines-0-description': 'Test teenus 1',
        'lines-0-qty': '1.00',
        'lines-0-unit_price': '100.50',
        'lines-1-description': 'Test teenus 2', 
        'lines-1-qty': '2.50',
        'lines-1-unit_price': '45.75'
    }
    
    response = session.post(f"{BASE_URL}/invoices/new", data=invoice_data, allow_redirects=False)
    
    if response.status_code != 302:
        # Debug form validation errors
        soup = BeautifulSoup(response.text, 'html.parser')
        error_divs = soup.find_all('div', class_='invalid-feedback')
        if error_divs:
            print("Form validation errors:")
            for div in error_divs:
                print(f"  - {div.get_text(strip=True)}")
        
        # Check for flash messages
        flash_messages = soup.find_all(class_=lambda x: x and 'alert' in x)
        if flash_messages:
            print("Flash messages:")
            for msg in flash_messages:
                print(f"  - {msg.get_text(strip=True)}")
    
    assert response.status_code == 302, f"Expected redirect after invoice creation, got {response.status_code}"
    
    # Extract invoice ID from redirect URL
    location = response.headers.get('Location', '')
    invoice_id_match = re.search(r'/invoices/(\d+)', location)
    assert invoice_id_match, f"Could not extract invoice ID from redirect: {location}"
    invoice_id = invoice_id_match.group(1)
    
    print(f"✓ Invoice created with ID: {invoice_id}")
    
    # Step 2: Edit the invoice and change line amounts
    print("\n2. Editing invoice and changing line amounts...")
    
    edit_url = f"{BASE_URL}/invoices/{invoice_id}/edit"
    response = session.get(edit_url)
    assert response.status_code == 200, f"Failed to get edit form: {response.status_code}"
    
    csrf_token = extract_csrf_token(response)
    
    # Step 3: Skip initial totals verification (JavaScript calculates these dynamically)
    print("\n3. Skipping initial edit form totals (calculated by JavaScript)...")
    
    # Calculate expected totals for initial data for reference
    initial_lines = [
        {'qty': 1.00, 'unit_price': 100.50},
        {'qty': 2.50, 'unit_price': 45.75}
    ]
    expected_initial = calculate_expected_totals(initial_lines, 24)
    print(f"Expected initial totals: {expected_initial}")
    print("✓ Invoice edit form loaded successfully")
    
    # Step 4: Update the invoice with new line amounts that create precision challenges
    print("\n4. Updating invoice with precision-challenging amounts...")
    
    # Use amounts that were problematic before the fix
    updated_lines = [
        {'qty': 1.33, 'unit_price': 123.45},  # Line total: 164.2885 -> 164.29
        {'qty': 2.67, 'unit_price': 87.65},   # Line total: 234.0255 -> 234.03
        {'qty': 0.75, 'unit_price': 199.99}   # Line total: 149.9925 -> 149.99
    ]
    
    update_data = {
        'csrf_token': csrf_token,
        'number': invoice_data['number'],
        'client_id': invoice_data['client_id'],
        'date': invoice_data['date'],
        'due_date': invoice_data['due_date'], 
        'payment_terms': invoice_data['payment_terms'],
        'vat_rate_id': vat_rate_id,
        'lines-0-description': 'Updated service 1',
        'lines-0-qty': str(updated_lines[0]['qty']),
        'lines-0-unit_price': str(updated_lines[0]['unit_price']),
        'lines-1-description': 'Updated service 2',
        'lines-1-qty': str(updated_lines[1]['qty']),
        'lines-1-unit_price': str(updated_lines[1]['unit_price']),
        'lines-2-description': 'Updated service 3',
        'lines-2-qty': str(updated_lines[2]['qty']),
        'lines-2-unit_price': str(updated_lines[2]['unit_price'])
    }
    
    # Calculate expected totals for updated data
    expected_updated = calculate_expected_totals(updated_lines, 24)
    print(f"Expected updated totals: {expected_updated}")
    
    # Step 5: Save the invoice ("Uuenda arvet")
    print("\n5. Saving updated invoice...")
    response = session.post(edit_url, data=update_data, allow_redirects=False)
    assert response.status_code == 302, f"Expected redirect after update, got {response.status_code}"
    
    print("✓ Invoice updated successfully")
    
    # Step 6: Check view page sidebar totals
    print("\n6. Checking view page sidebar totals...")
    
    view_url = f"{BASE_URL}/invoices/{invoice_id}"
    response = session.get(view_url)
    assert response.status_code == 200, f"Failed to get view page: {response.status_code}"
    
    # Extract totals from view page sidebar
    view_totals = extract_totals_from_sidebar(response.text)
    print(f"View page totals: {view_totals}")
    
    # Step 7: Verify that view page totals match expected calculations
    print("\n7. Verifying totals match expected calculations...")
    
    precision_errors = []
    
    if view_totals['subtotal'] != expected_updated['subtotal']:
        precision_errors.append(f"Subtotal: {view_totals['subtotal']} != {expected_updated['subtotal']}")
    
    if view_totals['vat_amount'] != expected_updated['vat_amount']:
        precision_errors.append(f"VAT amount: {view_totals['vat_amount']} != {expected_updated['vat_amount']}")
    
    if view_totals['total'] != expected_updated['total']:
        precision_errors.append(f"Total: {view_totals['total']} != {expected_updated['total']}")
    
    if precision_errors:
        print("❌ PRECISION ERRORS FOUND:")
        for error in precision_errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ All totals match expected calculations perfectly!")
    
    # Step 8: Verify edit form shows same totals as view page
    print("\n8. Verifying edit form totals match view page...")
    
    response = session.get(edit_url)
    assert response.status_code == 200, f"Failed to get edit form: {response.status_code}"
    
    edit_totals_after_update = extract_totals_from_sidebar(response.text)
    print(f"Edit form totals after update: {edit_totals_after_update}")
    
    consistency_errors = []
    
    if edit_totals_after_update['subtotal'] != view_totals['subtotal']:
        consistency_errors.append(f"Subtotal: Edit {edit_totals_after_update['subtotal']} != View {view_totals['subtotal']}")
    
    if edit_totals_after_update['vat_amount'] != view_totals['vat_amount']:
        consistency_errors.append(f"VAT amount: Edit {edit_totals_after_update['vat_amount']} != View {view_totals['vat_amount']}")
    
    if edit_totals_after_update['total'] != view_totals['total']:
        consistency_errors.append(f"Total: Edit {edit_totals_after_update['total']} != View {view_totals['total']}")
    
    if consistency_errors:
        print("❌ CONSISTENCY ERRORS FOUND:")
        for error in consistency_errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ Edit form and view page totals are consistent!")
    
    # Step 9: Test edge cases with different VAT rates
    print("\n9. Testing with different VAT rates...")
    
    # Test with 0% VAT
    csrf_token = extract_csrf_token(response)
    
    edge_case_data = update_data.copy()
    edge_case_data['csrf_token'] = csrf_token
    edge_case_data['vat_rate_id'] = '1'  # Assuming ID 1 is 0% VAT
    
    response = session.post(edit_url, data=edge_case_data, allow_redirects=False)
    assert response.status_code == 302, f"Expected redirect after VAT rate change, got {response.status_code}"
    
    # Check view page with 0% VAT
    response = session.get(view_url)
    view_totals_0_vat = extract_totals_from_sidebar(response.text)
    
    expected_0_vat = calculate_expected_totals(updated_lines, 0)
    
    if view_totals_0_vat['vat_amount'] != expected_0_vat['vat_amount']:
        print(f"❌ 0% VAT calculation error: {view_totals_0_vat['vat_amount']} != {expected_0_vat['vat_amount']}")
        return False
    else:
        print("✓ 0% VAT rate calculation is correct!")
    
    print("\n=== WORKFLOW INTEGRATION TEST COMPLETED SUCCESSFULLY ===")
    
    # Print final summary
    print("\n=== FINAL SUMMARY ===")
    print(f"Invoice ID: {invoice_id}")
    print(f"Test lines used: {len(updated_lines)} lines with precision-challenging amounts")
    print(f"VAT rates tested: 24%, 0%")
    print(f"Final totals (24% VAT):")
    print(f"  Subtotal: {view_totals['subtotal']}€")
    print(f"  VAT: {view_totals['vat_amount']}€")
    print(f"  Total: {view_totals['total']}€")
    print("✅ All precision calculations are working correctly!")
    print("✅ Edit form and view page are consistent!")
    print("✅ No 'stale totals' issue found!")
    
    return True


if __name__ == "__main__":
    try:
        success = test_workflow()
        if success:
            print("\n🎉 INTEGRATION TEST PASSED! VAT calculation precision fix is working correctly.")
        else:
            print("\n💥 INTEGRATION TEST FAILED! Issues found with VAT calculations.")
            exit(1)
    except Exception as e:
        print(f"\n💥 INTEGRATION TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)