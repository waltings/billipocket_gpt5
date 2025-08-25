#!/usr/bin/env python3
"""
Test for the exact issue: view page shows stale totals after successful edit.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def test_exact_issue():
    """Test the exact issue described by the user."""
    print("=== TESTING EXACT ISSUE: Stale totals in view page ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Use an existing invoice
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found")
                return
            
            print(f"📋 Using Invoice #{invoice.id}: {invoice.number}")
            
            # Record original state
            original_values = {
                'subtotal': invoice.subtotal,
                'total': invoice.total,
                'line_values': [(line.qty, line.unit_price, line.line_total) for line in invoice.lines]
            }
            
            print(f"\n📊 ORIGINAL STATE:")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   VAT Amount: €{invoice.vat_amount}")
            print(f"   Total: €{invoice.total}")
            
            # Step 1: Simulate edit - change a line amount
            print(f"\n1️⃣ EDITING: Changing first line price €{invoice.lines[0].unit_price} → €999.99")
            
            first_line = invoice.lines[0]
            first_line.unit_price = Decimal('999.99')
            first_line.line_total = first_line.qty * first_line.unit_price
            
            # Step 2: Simulate the edit_invoice workflow
            print(f"2️⃣ SIMULATING edit_invoice workflow...")
            
            # Flush (line 620 in edit_invoice)
            db.session.flush()
            
            # Calculate totals (line 623 in edit_invoice)
            calculate_invoice_totals(invoice)
            
            print(f"   After calculate_invoice_totals:")
            print(f"     Subtotal: €{invoice.subtotal}")
            print(f"     Total: €{invoice.total}")
            
            # Commit (line 626 in edit_invoice)
            db.session.commit()
            
            # Refresh (line 630 in edit_invoice)
            try:
                db.session.refresh(invoice)
                print(f"   After refresh:")
                print(f"     Subtotal: €{invoice.subtotal}")
                print(f"     Total: €{invoice.total}")
            except Exception as e:
                print(f"   Refresh error: {e}")
            
            # Step 3: Simulate redirect to view_invoice
            print(f"\n3️⃣ SIMULATING view_invoice (what user sees)...")
            
            # This is the EXACT same query that view_invoice uses
            view_invoice_data = Invoice.query.get_or_404(invoice.id)
            
            print(f"   View page would show:")
            print(f"     Subtotal: €{view_invoice_data.subtotal}")
            print(f"     VAT Amount: €{view_invoice_data.vat_amount}")
            print(f"     Total: €{view_invoice_data.total}")
            
            # Step 4: Check if there's a discrepancy
            print(f"\n4️⃣ DISCREPANCY CHECK:")
            
            # Compare what edit_invoice calculated vs what view_invoice shows
            edit_calculated_total = invoice.total
            view_displayed_total = view_invoice_data.total
            
            if abs(edit_calculated_total - view_displayed_total) < Decimal('0.01'):
                print(f"   ✅ NO DISCREPANCY: Edit and view totals match")
                print(f"      Edit calculated: €{edit_calculated_total}")
                print(f"      View displays: €{view_displayed_total}")
            else:
                print(f"   ❌ DISCREPANCY FOUND!")
                print(f"      Edit calculated: €{edit_calculated_total}")
                print(f"      View displays: €{view_displayed_total}")
                print(f"      Difference: €{abs(edit_calculated_total - view_displayed_total)}")
            
            # Step 5: Test if object identity is the issue
            print(f"\n5️⃣ OBJECT IDENTITY CHECK:")
            print(f"   Same object instance: {invoice is view_invoice_data}")
            print(f"   Invoice object ID: {id(invoice)}")
            print(f"   View invoice object ID: {id(view_invoice_data)}")
            
            # Step 6: Test VAT amount calculation consistency
            print(f"\n6️⃣ VAT AMOUNT CALCULATION CHECK:")
            
            # Method 1: Using property (what template uses)
            vat_via_property = view_invoice_data.vat_amount
            
            # Method 2: Manual calculation (what totals service would calculate)
            vat_manual = view_invoice_data.subtotal * (Decimal(str(view_invoice_data.vat_rate)) / Decimal('100'))
            
            # Method 3: Using totals service
            temp_result = calculate_invoice_totals(view_invoice_data)
            vat_via_service = temp_result['vat_amount']
            
            print(f"   VAT via property: €{vat_via_property}")
            print(f"   VAT manual calc: €{vat_manual}")
            print(f"   VAT via service: €{vat_via_service}")
            
            vat_methods_match = (
                abs(vat_via_property - vat_manual) < Decimal('0.01') and
                abs(vat_via_property - vat_via_service) < Decimal('0.01')
            )
            
            print(f"   VAT calculations match: {'Yes ✅' if vat_methods_match else 'No ❌'}")
            
            if not vat_methods_match:
                print(f"   ⚠️  POTENTIAL ISSUE: Inconsistent VAT calculation methods")
                print(f"      This could cause user confusion!")
            
            # Step 7: Test with session clearing (simulate new HTTP request)
            print(f"\n7️⃣ SESSION CLEARING TEST (simulate new request):")
            
            # Clear session to simulate new HTTP request context
            db.session.expunge_all()
            
            # Load invoice fresh (like a new HTTP request would)
            fresh_invoice = Invoice.query.get_or_404(invoice.id)
            
            print(f"   Fresh request would show:")
            print(f"     Subtotal: €{fresh_invoice.subtotal}")
            print(f"     Total: €{fresh_invoice.total}")
            
            # Step 8: Restore original state
            print(f"\n8️⃣ RESTORING ORIGINAL STATE...")
            
            # Restore values
            for i, (orig_qty, orig_price, orig_total) in enumerate(original_values['line_values']):
                fresh_invoice.lines[i].qty = orig_qty
                fresh_invoice.lines[i].unit_price = orig_price
                fresh_invoice.lines[i].line_total = orig_total
            
            fresh_invoice.subtotal = original_values['subtotal']
            fresh_invoice.total = original_values['total']
            
            db.session.commit()
            print(f"   ✅ Restored to original state")
            
            # Final conclusion
            print(f"\n🎯 CONCLUSION:")
            if view_displayed_total == edit_calculated_total:
                print(f"   ✅ Backend calculations are CONSISTENT")
                print(f"   🤔 Issue might be:")
                print(f"      - Browser caching")
                print(f"      - User not refreshing page properly") 
                print(f"      - Expecting JavaScript values vs server values")
                print(f"      - Template rendering issue")
                print(f"      - VAT amount display precision (property vs service)")
            else:
                print(f"   ❌ CONFIRMED BUG: Backend calculations are INCONSISTENT")
                print(f"   🐛 Root cause identified in edit-to-view workflow")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_exact_issue()