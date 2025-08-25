#!/usr/bin/env python3
"""
Comprehensive test of the invoice editing workflow
"""
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine
from flask import url_for

def test_invoice_editing_http_workflow():
    """Test the actual HTTP workflow with form submission."""
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    with app.test_client() as client:
        with app.app_context():
            # Get an invoice to test with
            invoice = Invoice.query.first()
            if not invoice or not invoice.lines:
                print("No suitable test invoice found")
                return
                
            print(f"=== Testing Invoice {invoice.number} via HTTP ===")
            
            # Step 1: Get the edit form
            print(f"1. Getting edit form...")
            edit_url = f'/invoices/{invoice.id}/edit'
            response = client.get(edit_url)
            print(f"   Edit form response: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   ERROR: Could not get edit form")
                return
            
            # Step 2: Record initial state
            initial_subtotal = float(invoice.subtotal)
            initial_total = float(invoice.total)
            initial_vat_amount = float(invoice.vat_amount)
            
            print(f"   Initial state:")
            print(f"     Subtotal: {initial_subtotal}")
            print(f"     VAT: {initial_vat_amount}")
            print(f"     Total: {initial_total}")
            
            # Step 3: Prepare form data for submission (modify line quantities)
            form_data = {
                'number': invoice.number,
                'client_id': invoice.client_id,
                'date': invoice.date.strftime('%Y-%m-%d'),
                'due_date': invoice.due_date.strftime('%Y-%m-%d'),
                'status': invoice.status,
                'payment_terms': invoice.payment_terms or '',
                'client_extra_info': invoice.client_extra_info or '',
                'note': invoice.note or '',
                'announcements': invoice.announcements or '',
                'pdf_template': invoice.pdf_template or 'standard',
                'vat_rate_id': invoice.vat_rate_id or '1'
            }
            
            # Add line data with modified quantities
            for i, line in enumerate(invoice.lines):
                # Double the quantity to create a significant change
                new_qty = float(line.qty) * 2
                new_line_total = new_qty * float(line.unit_price)
                
                form_data.update({
                    f'lines-{i}-id': str(line.id),
                    f'lines-{i}-description': line.description,
                    f'lines-{i}-qty': str(new_qty),
                    f'lines-{i}-unit_price': str(line.unit_price),
                    f'lines-{i}-line_total': str(new_line_total)
                })
            
            print(f"2. Submitting modified form (doubling quantities)...")
            print(f"   Form data lines:")
            for i, line in enumerate(invoice.lines):
                new_qty = float(line.qty) * 2
                print(f"     Line {i+1}: qty {line.qty} -> {new_qty}")
            
            # Step 4: Submit the form
            response = client.post(edit_url, data=form_data, follow_redirects=False)
            print(f"   Form submission response: {response.status_code}")
            
            if response.status_code == 302:
                redirect_url = response.headers.get('Location')
                print(f"   Redirected to: {redirect_url}")
            elif response.status_code == 200:
                print(f"   Form submission stayed on same page (likely validation error)")
                return
            else:
                print(f"   Unexpected response code: {response.status_code}")
                return
            
            # Step 5: Check invoice state after submission
            # Refresh the invoice from database
            db.session.expunge_all()  # Clear session cache
            updated_invoice = Invoice.query.get(invoice.id)
            
            new_subtotal = float(updated_invoice.subtotal)
            new_total = float(updated_invoice.total)
            new_vat_amount = float(updated_invoice.vat_amount)
            
            print(f"3. Invoice state after form submission:")
            print(f"   New subtotal: {new_subtotal}")
            print(f"   New VAT: {new_vat_amount}")
            print(f"   New total: {new_total}")
            
            # Step 6: Follow the redirect to see what user sees
            if response.status_code == 302:
                print(f"4. Following redirect to invoice view...")
                redirect_response = client.get(redirect_url)
                print(f"   Invoice view response: {redirect_response.status_code}")
                
                if redirect_response.status_code == 200:
                    # Check if the invoice data in the view is correct
                    # Re-query the invoice to simulate fresh page load
                    db.session.expunge_all()
                    view_invoice = Invoice.query.get(invoice.id)
                    
                    view_subtotal = float(view_invoice.subtotal)
                    view_total = float(view_invoice.total) 
                    view_vat_amount = float(view_invoice.vat_amount)
                    
                    print(f"   Invoice data in view:")
                    print(f"     Subtotal: {view_subtotal}")
                    print(f"     VAT: {view_vat_amount}")
                    print(f"     Total: {view_total}")
                    
                    # Check if sidebar would be correct
                    expected_subtotal = initial_subtotal * 2  # We doubled quantities
                    expected_vat = expected_subtotal * 0.24   # 24% VAT
                    expected_total = expected_subtotal + expected_vat
                    
                    print(f"5. Expected vs Actual:")
                    print(f"   Expected subtotal: {expected_subtotal}, Got: {view_subtotal}")
                    print(f"   Expected VAT: {expected_vat}, Got: {view_vat_amount}")  
                    print(f"   Expected total: {expected_total}, Got: {view_total}")
                    
                    # Tolerance check
                    tolerance = 0.01
                    subtotal_ok = abs(view_subtotal - expected_subtotal) < tolerance
                    vat_ok = abs(view_vat_amount - expected_vat) < tolerance
                    total_ok = abs(view_total - expected_total) < tolerance
                    
                    if subtotal_ok and vat_ok and total_ok:
                        print(f"✅ SUCCESS: Sidebar should update correctly!")
                    else:
                        print(f"❌ PROBLEM: Sidebar totals would be incorrect!")
                        print(f"   Subtotal correct: {subtotal_ok}")
                        print(f"   VAT correct: {vat_ok}")
                        print(f"   Total correct: {total_ok}")
                        
            # Step 7: Restore original state
            print(f"6. Restoring original state...")
            for line in updated_invoice.lines:
                line.qty /= 2
                line.line_total = line.qty * line.unit_price
            
            from app.services.totals import calculate_invoice_totals
            calculate_invoice_totals(updated_invoice)
            db.session.commit()
            print(f"   Original state restored")

if __name__ == "__main__":
    test_invoice_editing_http_workflow()