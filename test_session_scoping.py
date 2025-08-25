#!/usr/bin/env python3
"""
Test for session scoping issues that might cause stale data in view_invoice.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def test_session_scoping_issue():
    """Test if there are session scoping issues causing stale data."""
    print("=== TESTING SESSION SCOPING ISSUE ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get an invoice
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found in database.")
                return
                
            invoice_id = invoice.id
            print(f"📋 Testing with Invoice #{invoice_id}")
            
            # Show current state
            print(f"\n📊 CURRENT STATE:")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   Total: €{invoice.total}")
            
            # Simulate what edit_invoice does in detail
            print(f"\n🔧 SIMULATING edit_invoice POST REQUEST:")
            
            # 1. Modify a line (simulating form submission)
            first_line = invoice.lines[0]
            original_price = first_line.unit_price
            original_line_total = first_line.line_total
            original_subtotal = invoice.subtotal
            original_total = invoice.total
            
            print(f"   1. Modifying line price: €{first_line.unit_price} → €150.00")
            first_line.unit_price = Decimal('150.00')
            first_line.line_total = first_line.qty * first_line.unit_price
            
            # 2. Flush (like edit_invoice does on line 620)
            print(f"   2. Flushing changes...")
            db.session.flush()
            
            # 3. Recalculate totals (like edit_invoice does on line 623)
            print(f"   3. Recalculating totals...")
            calculate_invoice_totals(invoice)
            
            # 4. Commit (like edit_invoice does on line 626)
            print(f"   4. Committing changes...")
            db.session.commit()
            
            print(f"   After edit - Subtotal: €{invoice.subtotal}, Total: €{invoice.total}")
            
            # 5. Refresh (like edit_invoice does on line 630)
            print(f"   5. Refreshing invoice...")
            try:
                db.session.refresh(invoice)
                print(f"   After refresh - Subtotal: €{invoice.subtotal}, Total: €{invoice.total}")
            except Exception as e:
                print(f"   Refresh failed: {e}")
            
            print(f"\n🌐 SIMULATING NEW HTTP REQUEST (view_invoice):")
            
            # This simulates a completely new HTTP request where view_invoice is called
            # In a real Flask app, this would be a new request context
            
            # Method 1: Direct query (what view_invoice does)
            print(f"   Method 1: Direct query")
            fresh_invoice_1 = Invoice.query.get_or_404(invoice_id)
            print(f"     Subtotal: €{fresh_invoice_1.subtotal}")
            print(f"     Total: €{fresh_invoice_1.total}")
            print(f"     Lines loaded: {len(fresh_invoice_1.lines)}")
            
            # Method 2: Query with explicit relationship loading
            print(f"   Method 2: Query with eager loading")
            fresh_invoice_2 = Invoice.query.options(db.joinedload(Invoice.lines)).get_or_404(invoice_id)
            print(f"     Subtotal: €{fresh_invoice_2.subtotal}")
            print(f"     Total: €{fresh_invoice_2.total}")
            print(f"     Lines loaded: {len(fresh_invoice_2.lines)}")
            
            # Method 3: Clear session and query again
            print(f"   Method 3: Clear session and query")
            db.session.expunge_all()  # Clear all objects from session
            fresh_invoice_3 = Invoice.query.get_or_404(invoice_id)
            print(f"     Subtotal: €{fresh_invoice_3.subtotal}")
            print(f"     Total: €{fresh_invoice_3.total}")
            print(f"     Lines loaded: {len(fresh_invoice_3.lines)}")
            
            # Check if all methods return the same values
            methods_match = (
                fresh_invoice_1.subtotal == fresh_invoice_2.subtotal == fresh_invoice_3.subtotal and
                fresh_invoice_1.total == fresh_invoice_2.total == fresh_invoice_3.total
            )
            
            print(f"\n🔍 ANALYSIS:")
            print(f"   All methods return same values: {'Yes ✅' if methods_match else 'No ❌'}")
            
            if not methods_match:
                print(f"   ❌ INCONSISTENT VALUES DETECTED!")
                print(f"      Method 1 (direct): Subtotal=€{fresh_invoice_1.subtotal}, Total=€{fresh_invoice_1.total}")
                print(f"      Method 2 (eager): Subtotal=€{fresh_invoice_2.subtotal}, Total=€{fresh_invoice_2.total}")
                print(f"      Method 3 (cleared): Subtotal=€{fresh_invoice_3.subtotal}, Total=€{fresh_invoice_3.total}")
            
            # Test what happens if we calculate totals on fresh invoice
            print(f"\n🧮 TESTING MANUAL CALCULATION ON FRESH INVOICE:")
            manual_subtotal = sum(Decimal(str(line.line_total)) for line in fresh_invoice_3.lines)
            manual_vat = manual_subtotal * (Decimal(str(fresh_invoice_3.vat_rate)) / Decimal('100'))
            manual_total = manual_subtotal + manual_vat
            
            print(f"   Manual from lines: Subtotal=€{manual_subtotal}, Total=€{manual_total}")
            print(f"   DB stored values: Subtotal=€{fresh_invoice_3.subtotal}, Total=€{fresh_invoice_3.total}")
            
            values_match = (
                abs(float(fresh_invoice_3.subtotal) - float(manual_subtotal)) < 0.01 and
                abs(float(fresh_invoice_3.total) - float(manual_total)) < 0.01
            )
            
            if values_match:
                print(f"   ✅ DB values match manual calculation")
            else:
                print(f"   ❌ DB VALUES DON'T MATCH MANUAL CALCULATION!")
                print(f"      This indicates the invoice totals weren't properly updated in the database")
            
            # Restore original values
            print(f"\n🔄 RESTORING ORIGINAL VALUES...")
            first_line.unit_price = original_price
            first_line.line_total = original_line_total
            fresh_invoice_3.subtotal = original_subtotal
            fresh_invoice_3.total = original_total
            db.session.commit()
            print(f"   ✅ Restored to original state")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_session_scoping_issue()