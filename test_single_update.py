#!/usr/bin/env python3
"""
Simple test to create and update a single invoice to debug the totals issue.
"""

import requests
import time
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5010"
session = requests.Session()

def extract_csrf_token(response):
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    return csrf_input.get('value') if csrf_input else None

# Create invoice
print("Creating invoice...")
response = session.get(f"{BASE_URL}/invoices/new")
csrf_token = extract_csrf_token(response)

soup = BeautifulSoup(response.text, 'html.parser')
client_select = soup.find('select', {'name': 'client_id'})
clients = [opt.get('value') for opt in client_select.find_all('option') if opt.get('value')]

invoice_data = {
    'csrf_token': csrf_token,
    'number': f'2025-{int(time.time()) % 10000:04d}',
    'client_id': clients[0],
    'date': '2025-08-14',
    'due_date': '2025-08-28',
    'payment_terms': '14 päeva',
    'vat_rate_id': '4',
    'lines-0-description': 'Test line',
    'lines-0-qty': '2.0',
    'lines-0-unit_price': '100.0'
}

response = session.post(f"{BASE_URL}/invoices/new", data=invoice_data, allow_redirects=False)
if response.status_code == 302:
    import re
    location = response.headers.get('Location', '')
    invoice_id_match = re.search(r'/invoices/(\d+)', location)
    if invoice_id_match:
        invoice_id = invoice_id_match.group(1)
        print(f"Created invoice {invoice_id}")
        
        # Update invoice
        print("Updating invoice...")
        edit_url = f"{BASE_URL}/invoices/{invoice_id}/edit"
        response = session.get(edit_url)
        csrf_token = extract_csrf_token(response)
        
        update_data = {
            'csrf_token': csrf_token,
            'number': invoice_data['number'],
            'client_id': invoice_data['client_id'],
            'date': invoice_data['date'],
            'due_date': invoice_data['due_date'], 
            'payment_terms': invoice_data['payment_terms'],
            'vat_rate_id': '4',
            'lines-0-description': 'Updated line',
            'lines-0-qty': '3.0',
            'lines-0-unit_price': '150.0'
        }
        
        response = session.post(edit_url, data=update_data, allow_redirects=False)
        if response.status_code == 302:
            print("Invoice updated successfully")
            
            # Check view page
            view_url = f"{BASE_URL}/invoices/{invoice_id}"
            response = session.get(view_url)
            
            # Extract totals
            soup = BeautifulSoup(response.text, 'html.parser')
            subtotal_elem = soup.find('td', string='Vahesumma:')
            if subtotal_elem:
                subtotal_text = subtotal_elem.find_next_sibling('td').get_text(strip=True)
                print(f"View page subtotal: {subtotal_text}")
                
                # Expected: 3.0 * 150.0 = 450.00
                print(f"Expected subtotal: 450.00€")
            else:
                print("Could not find subtotal on view page")
        else:
            print(f"Update failed: {response.status_code}")
    else:
        print("Could not extract invoice ID")
else:
    print(f"Creation failed: {response.status_code}")