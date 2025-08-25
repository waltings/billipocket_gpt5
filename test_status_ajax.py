#!/usr/bin/env python3
"""
Quick test to verify the AJAX status change functionality works correctly.
"""

import requests
import re
import sys
from bs4 import BeautifulSoup

BASE_URL = 'http://127.0.0.1:5000'

def extract_csrf_token(html_content):
    """Extract CSRF token from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    csrf_meta = soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta:
        return csrf_meta.get('content')
    
    # Fallback: look for csrf_token in forms
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    if csrf_input:
        return csrf_input.get('value')
    return None

def test_ajax_status_change():
    """Test AJAX status change functionality"""
    print("Testing AJAX Status Change Functionality...")
    
    session = requests.Session()
    
    try:
        # Get invoices list page to find an invoice
        print("1. Getting invoices list...")
        response = session.get(f"{BASE_URL}/invoices")
        if response.status_code != 200:
            print(f"❌ Failed to get invoices list: {response.status_code}")
            return False
        
        # Extract CSRF token
        csrf_token = extract_csrf_token(response.text)
        if not csrf_token:
            print("❌ No CSRF token found")
            return False
        print(f"✅ CSRF token found: {csrf_token[:20]}...")
        
        # Find first invoice ID in the table
        soup = BeautifulSoup(response.text, 'html.parser')
        clickable_badge = soup.find('span', class_='clickable-status')
        if not clickable_badge:
            print("❌ No clickable status badges found")
            return False
        
        invoice_id = clickable_badge.get('data-invoice-id')
        if not invoice_id:
            print("❌ No invoice ID found in badge")
            return False
        
        current_status = clickable_badge.text.strip()
        print(f"✅ Found invoice {invoice_id} with status: {current_status}")
        
        # Determine new status for testing
        new_status = 'makstud' if current_status in ['Maksmata', 'Tähtaeg ületatud'] else 'maksmata'
        print(f"2. Testing status change from '{current_status}' to '{new_status}'...")
        
        # Make AJAX request to change status
        response = session.post(
            f"{BASE_URL}/invoices/{invoice_id}/status/{new_status}",
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={'csrf_token': csrf_token}
        )
        
        if response.status_code != 200:
            print(f"❌ AJAX request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Parse JSON response
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ Failed to parse JSON response: {e}")
            print(f"Response text: {response.text}")
            return False
        
        if not data.get('success'):
            print(f"❌ Status change failed: {data.get('message', 'Unknown error')}")
            return False
        
        print("✅ AJAX status change successful!")
        print(f"   New status: {data.get('status_display')}")
        print(f"   Message: {data.get('message')}")
        print(f"   Status color: {data.get('status_color')}")
        
        # Test changing back
        print("3. Testing status change back...")
        reverse_status = 'maksmata' if new_status == 'makstud' else 'makstud'
        
        response = session.post(
            f"{BASE_URL}/invoices/{invoice_id}/status/{reverse_status}",
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={'csrf_token': csrf_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Reverse status change successful!")
            else:
                print(f"❌ Reverse status change failed: {data.get('message')}")
        else:
            print(f"❌ Reverse AJAX request failed: {response.status_code}")
        
        # Test non-AJAX request (should redirect)
        print("4. Testing regular POST request (should redirect)...")
        response = session.post(
            f"{BASE_URL}/invoices/{invoice_id}/status/{new_status}",
            data={'csrf_token': csrf_token},
            allow_redirects=False
        )
        
        if response.status_code in [302, 303]:
            print("✅ Regular POST request correctly redirects!")
            print(f"   Redirect location: {response.headers.get('Location')}")
        else:
            print(f"❌ Regular POST request should redirect, got: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

if __name__ == '__main__':
    print("🧪 AJAX Status Change Test")
    print("=" * 40)
    
    success = test_ajax_status_change()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)