#!/usr/bin/env python3
"""
Test script to reproduce the sidebar summary update issue
"""
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine
from app.services.totals import calculate_invoice_totals
from decimal import Decimal

def test_invoice_editing_workflow():
    """Simulate the exact invoice editing workflow."""
    
    app = create_app()
    with app.app_context():
        # Get a test invoice
        invoice = Invoice.query.first()
        if not invoice or not invoice.lines:
            print("No suitable test invoice found")
            return
            
        print(f"=== Testing Invoice {invoice.number} ===")
        print(f"Initial state:")
        print(f"  Lines: {[(line.description[:20], line.qty, line.unit_price, line.line_total) for line in invoice.lines]}")
        print(f"  Subtotal: {invoice.subtotal}")
        print(f"  VAT Amount (property): {invoice.vat_amount}")
        print(f"  Total: {invoice.total}")
        
        # Simulate user editing: change quantities
        print(f"\n=== Simulating Edit: Doubling quantities ===")
        original_line_totals = []
        for line in invoice.lines:
            original_line_totals.append(line.line_total)
            # Double the quantity (simulate user editing)
            line.qty *= 2
            line.line_total = line.qty * line.unit_price
            print(f"  Updated line: {line.description[:20]} - qty: {line.qty}, line_total: {line.line_total}")
        
        # Simulate the calculate_invoice_totals call from edit_invoice()
        print(f"\n=== Calling calculate_invoice_totals() ===")
        result = calculate_invoice_totals(invoice)
        print(f"  Calculation result: {result}")
        
        print(f"\n=== Invoice state after calculate_invoice_totals() ===")
        print(f"  Subtotal: {invoice.subtotal}")
        print(f"  VAT Amount (property): {invoice.vat_amount}")
        print(f"  Total: {invoice.total}")
        
        # Simulate database commit
        print(f"\n=== Simulating db.session.commit() ===")
        try:
            db.session.commit()
            print("  Commit successful")
        except Exception as e:
            print(f"  Commit failed: {e}")
            db.session.rollback()
        
        # Simulate redirect and fresh page load (new query)
        print(f"\n=== Simulating fresh page load (redirect to invoice view) ===")
        fresh_invoice = Invoice.query.get(invoice.id)
        print(f"  Fresh invoice subtotal: {fresh_invoice.subtotal}")
        print(f"  Fresh invoice VAT amount (property): {fresh_invoice.vat_amount}")
        print(f"  Fresh invoice total: {fresh_invoice.total}")
        
        # Check for discrepancy
        if (fresh_invoice.subtotal != result['subtotal'] or 
            fresh_invoice.total != result['total'] or
            abs(fresh_invoice.vat_amount - result['vat_amount']) > Decimal('0.01')):
            print(f"\n❌ DISCREPANCY FOUND!")
            print(f"  Expected subtotal: {result['subtotal']}, Got: {fresh_invoice.subtotal}")
            print(f"  Expected VAT: {result['vat_amount']}, Got: {fresh_invoice.vat_amount}")
            print(f"  Expected total: {result['total']}, Got: {fresh_invoice.total}")
        else:
            print(f"\n✅ All totals match - sidebar should update correctly")
        
        # Restore original state for next tests
        print(f"\n=== Restoring original state ===")
        for i, line in enumerate(invoice.lines):
            line.qty /= 2  # Restore original quantity
            line.line_total = original_line_totals[i]
        
        calculate_invoice_totals(invoice)
        db.session.commit()
        print("  Original state restored")

if __name__ == "__main__":
    test_invoice_editing_workflow()