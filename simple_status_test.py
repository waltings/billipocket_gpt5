#!/usr/bin/env python3
"""
Simple test to verify invoice status transitions work
"""

import requests
import sqlite3
import re
from datetime import datetime

BASE_URL = "http://localhost:5010"
DB_PATH = "/Users/keijovalting/Downloads/billipocket_gpt5/instance/billipocket.db"

def test_status_change():
    session = requests.Session()
    
    # Get an unpaid invoice
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, number, status FROM invoices WHERE status = 'maksmata' LIMIT 1")
    result = cursor.fetchone()
    
    if not result:
        print("No unpaid invoices found")
        return False
        
    invoice_id, invoice_number, original_status = result
    print(f"Testing with invoice {invoice_number} (ID: {invoice_id})")
    print(f"Original status: {original_status}")
    
    # Get the edit form
    edit_url = f"{BASE_URL}/invoices/{invoice_id}/edit"
    response = session.get(edit_url)
    
    if response.status_code != 200:
        print(f"Failed to get edit form: {response.status_code}")
        return False
    
    print(f"Got edit form: {response.status_code}")
    
    # Extract CSRF token and other form data
    content = response.text
    csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]*)"', content)
    
    if not csrf_match:
        print("Could not find CSRF token")
        return False
        
    csrf_token = csrf_match.group(1)
    print(f"CSRF token: {csrf_token[:20]}...")
    
    # Extract other required form fields
    form_data = {'csrf_token': csrf_token}
    
    # Look for hidden and visible form fields
    field_patterns = [
        (r'name="client_id"[^>]*selected[^>]*value="([^"]*)"', 'client_id'),
        (r'name="date"[^>]*value="([^"]*)"', 'date'),
        (r'name="due_date"[^>]*value="([^"]*)"', 'due_date'),
        (r'name="vat_rate_id"[^>]*value="([^"]*)"', 'vat_rate_id'),
        (r'name="number"[^>]*value="([^"]*)"', 'number'),
    ]
    
    # Also look for client_id in select options
    client_select_pattern = r'<select[^>]*name="client_id"[^>]*>(.*?)</select>'
    client_select_match = re.search(client_select_pattern, content, re.DOTALL)
    if client_select_match:
        option_pattern = r'<option[^>]*selected[^>]*value="(\d+)"'
        option_match = re.search(option_pattern, client_select_match.group(1))
        if option_match:
            form_data['client_id'] = option_match.group(1)
            print(f"Found client_id from select: {option_match.group(1)}")
    
    for pattern, field_name in field_patterns:
        match = re.search(pattern, content)
        if match:
            form_data[field_name] = match.group(1)
            print(f"Found {field_name}: {match.group(1)}")
    
    # Set the new status
    form_data['status'] = 'makstud'
    print(f"Changing status to: makstud")
    
    # Submit the form
    print("Submitting form...")
    response = session.post(edit_url, data=form_data, allow_redirects=False)
    print(f"Form submission response: {response.status_code}")
    
    if response.status_code == 302 or response.status_code == 303:
        print("✓ Form submitted successfully (redirect)")
        
        # Check database
        cursor.execute("SELECT status FROM invoices WHERE id = ?", (invoice_id,))
        new_status = cursor.fetchone()[0]
        print(f"New status in database: {new_status}")
        
        # Revert the change
        form_data['status'] = original_status
        session.post(edit_url, data=form_data)
        print(f"Reverted status back to: {original_status}")
        
        conn.close()
        return new_status == 'makstud'
    else:
        print(f"✗ Form submission failed: {response.status_code}")
        # Check if there are error messages in response
        if response.status_code == 200:
            # Look for validation errors
            error_patterns = [
                r'<div[^>]*alert[^>]*>(.*?)</div>',
                r'<span[^>]*invalid-feedback[^>]*>(.*?)</span>',
                r'<div[^>]*field-error[^>]*>(.*?)</div>',
                r'class="error"[^>]*>(.*?)</',
            ]
            
            found_errors = []
            for pattern in error_patterns:
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    clean_match = re.sub(r'<[^>]+>', '', match).strip()
                    if clean_match and len(clean_match) < 200:
                        found_errors.append(clean_match)
            
            if found_errors:
                print("Found validation errors:")
                for error in found_errors:
                    print(f"  - {error}")
            else:
                print("No clear error messages found in response")
                # Save response to file for inspection
                with open('/tmp/form_response.html', 'w') as f:
                    f.write(response.text)
                print("Response saved to /tmp/form_response.html for inspection")
        conn.close()
        return False

if __name__ == "__main__":
    success = test_status_change()
    print(f"\nTest result: {'PASS' if success else 'FAIL'}")