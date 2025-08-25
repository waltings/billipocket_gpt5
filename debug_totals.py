#!/usr/bin/env python3
"""
Debug script to test the calculate_invoice_totals function directly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app import create_app
from app.models import db, Invoice
from app.services.totals import calculate_invoice_totals

app = create_app()

with app.app_context():
    # Get invoice 8
    invoice = Invoice.query.get(8)
    
    if invoice:
        print("=== BEFORE CALCULATE_TOTALS ===")
        print(f"Invoice ID: {invoice.id}")
        print(f"Database subtotal: {invoice.subtotal}")
        print(f"Database total: {invoice.total}")
        print(f"VAT rate: {invoice.vat_rate}")
        print(f"VAT amount (property): {invoice.vat_amount}")
        
        print(f"\nLines ({len(invoice.lines)}):")
        expected_subtotal = 0
        for i, line in enumerate(invoice.lines):
            print(f"  Line {i+1}: {line.qty} × {line.unit_price} = {line.line_total}")
            expected_subtotal += line.line_total
        print(f"Expected subtotal: {expected_subtotal}")
        
        # Call calculate_invoice_totals
        print("\n=== CALLING CALCULATE_TOTALS ===")
        result = calculate_invoice_totals(invoice)
        print(f"Function result: {result}")
        
        print("\n=== AFTER CALCULATE_TOTALS (before commit) ===")
        print(f"Invoice subtotal: {invoice.subtotal}")
        print(f"Invoice total: {invoice.total}")
        print(f"VAT amount (property): {invoice.vat_amount}")
        
        # Test the changes without committing
        print("\n=== CHANGES MADE ===")
        if hasattr(invoice, 'subtotal') and invoice.subtotal != expected_subtotal:
            print(f"Subtotal was updated: {invoice.subtotal} (should be {expected_subtotal})")
        else:
            print("Subtotal matches expected value")
            
        # Commit changes
        db.session.commit()
        print("\n=== AFTER COMMIT ===")
        
        # Re-query to verify persistence
        invoice_fresh = Invoice.query.get(8)
        print(f"Fresh invoice subtotal: {invoice_fresh.subtotal}")
        print(f"Fresh invoice total: {invoice_fresh.total}")
        print(f"Fresh VAT amount (property): {invoice_fresh.vat_amount}")
        
    else:
        print("Invoice 8 not found")