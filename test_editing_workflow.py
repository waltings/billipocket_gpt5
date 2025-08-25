#!/usr/bin/env python3
"""
Test the complete editing workflow to reproduce the sidebar issue.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def test_editing_workflow():
    """Test the complete editing workflow to identify the sidebar issue."""
    print("=== TESTING EDITING WORKFLOW ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get an invoice to test with
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found in database.")
                return
            
            original_invoice_id = invoice.id
            print(f"📋 Testing with Invoice #{invoice.id}: {invoice.number}")
            
            # STEP 1: Show original state
            print(f"\n1️⃣ ORIGINAL STATE:")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   Total: €{invoice.total}")
            print(f"   Lines: {len(invoice.lines)}")
            for i, line in enumerate(invoice.lines):
                print(f"     Line {i+1}: {line.description[:30]}... qty={line.qty} price=€{line.unit_price} total=€{line.line_total}")
            
            # STEP 2: Simulate editing - modify a line amount
            print(f"\n2️⃣ SIMULATING EDIT: Changing first line price from €{invoice.lines[0].unit_price} to €150.00")
            
            # This simulates what happens in edit_invoice when form is submitted
            first_line = invoice.lines[0]
            old_price = first_line.unit_price
            old_line_total = first_line.line_total
            old_subtotal = invoice.subtotal
            old_total = invoice.total
            
            # Update the line (like edit_invoice does)
            first_line.unit_price = Decimal('150.00')
            first_line.line_total = first_line.qty * first_line.unit_price
            
            print(f"   Updated line: qty={first_line.qty} * price=€{first_line.unit_price} = €{first_line.line_total}")
            
            # Flush changes (like edit_invoice does)
            db.session.flush()
            
            # Recalculate totals (like edit_invoice does)
            calculate_invoice_totals(invoice)
            
            # Commit changes (like edit_invoice does)
            db.session.commit()
            
            print(f"   After calculate_invoice_totals:")
            print(f"     Subtotal: €{invoice.subtotal}")
            print(f"     Total: €{invoice.total}")
            
            # STEP 3: Simulate refresh (like edit_invoice does)
            print(f"\n3️⃣ SIMULATING REFRESH (like edit_invoice does):")
            try:
                db.session.refresh(invoice)
                print(f"   After refresh:")
                print(f"     Subtotal: €{invoice.subtotal}")
                print(f"     Total: €{invoice.total}")
            except Exception as refresh_error:
                print(f"   Refresh failed: {refresh_error}")
            
            # STEP 4: Simulate redirect to view_invoice
            print(f"\n4️⃣ SIMULATING REDIRECT TO view_invoice:")
            
            # This is what view_invoice does: Invoice.query.get_or_404(invoice_id)
            fresh_invoice = Invoice.query.get_or_404(original_invoice_id)
            
            print(f"   Fresh query result:")
            print(f"     Subtotal: €{fresh_invoice.subtotal}")
            print(f"     Total: €{fresh_invoice.total}")
            print(f"     Lines: {len(fresh_invoice.lines)}")
            
            # Check individual line values in fresh query
            for i, line in enumerate(fresh_invoice.lines):
                print(f"       Line {i+1}: qty={line.qty} price=€{line.unit_price} total=€{line.line_total}")
            
            # STEP 5: Verify what the template would see
            print(f"\n5️⃣ TEMPLATE SIDEBAR WOULD SHOW:")
            print(f"   {{ \"%.2f\"|format(invoice.subtotal) }}€ = €{fresh_invoice.subtotal}")
            print(f"   {{ \"%.2f\"|format(invoice.vat_amount) }}€ = €{fresh_invoice.vat_amount}")
            print(f"   {{ \"%.2f\"|format(invoice.total) }}€ = €{fresh_invoice.total}")
            
            # STEP 6: Manual verification by recalculating
            print(f"\n6️⃣ MANUAL VERIFICATION:")
            manual_subtotal = sum(Decimal(str(line.line_total)) for line in fresh_invoice.lines)
            manual_vat = manual_subtotal * (Decimal(str(fresh_invoice.vat_rate)) / Decimal('100'))
            manual_total = manual_subtotal + manual_vat
            
            print(f"   Manual calculation:")
            print(f"     Subtotal: €{manual_subtotal}")
            print(f"     VAT: €{manual_vat}")
            print(f"     Total: €{manual_total}")
            
            # Check for discrepancy
            db_vs_manual = (
                abs(float(fresh_invoice.subtotal) - float(manual_subtotal)) < 0.01 and
                abs(float(fresh_invoice.total) - float(manual_total)) < 0.01
            )
            
            if db_vs_manual:
                print(f"   ✅ Database values match manual calculation")
            else:
                print(f"   ❌ DATABASE VALUES DON'T MATCH MANUAL CALCULATION!")
                print(f"      This is the root cause of the sidebar issue!")
            
            # STEP 7: Test session identity and caching
            print(f"\n7️⃣ SESSION ANALYSIS:")
            
            # Check if both invoice objects are the same instance
            print(f"   Same object instance: {invoice is fresh_invoice}")
            print(f"   Invoice ID in session: {id(invoice)}")
            print(f"   Fresh invoice ID in session: {id(fresh_invoice)}")
            
            # Check session state
            print(f"   Session dirty objects: {len(db.session.dirty)}")
            print(f"   Session new objects: {len(db.session.new)}")
            print(f"   Session identity map size: {len(db.session.identity_map)}")
            
            # Restore original values for future tests
            print(f"\n🔄 RESTORING ORIGINAL VALUES:")
            first_line.unit_price = old_price
            first_line.line_total = old_line_total
            invoice.subtotal = old_subtotal
            invoice.total = old_total
            db.session.commit()
            print(f"   Restored to original state")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_editing_workflow()