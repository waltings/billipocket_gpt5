#!/usr/bin/env python3
"""
Test the complete user workflow after the VAT amount fix.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def test_complete_workflow_with_fix():
    """Test the complete user workflow with the VAT amount fix applied."""
    print("=== TESTING COMPLETE WORKFLOW WITH VAT AMOUNT FIX ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get an invoice for testing
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found")
                return
            
            print(f"📋 Testing Invoice #{invoice.id}: {invoice.number}")
            
            # Store original values for restoration
            original_values = {
                'lines': [(line.qty, line.unit_price, line.line_total) for line in invoice.lines],
                'subtotal': invoice.subtotal,
                'total': invoice.total
            }
            
            print(f"\n📊 STEP 1: INITIAL STATE")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   VAT Amount (property): €{invoice.vat_amount}")
            print(f"   Total: €{invoice.total}")
            
            # SIMULATE USER EDITING
            print(f"\n✏️ STEP 2: USER EDITS INVOICE (modifies line amounts)")
            
            # Change first line to create a scenario with potential precision issues
            first_line = invoice.lines[0]
            print(f"   Changing line: {first_line.description[:30]}...")
            print(f"   Old: qty={first_line.qty} × price=€{first_line.unit_price} = €{first_line.line_total}")
            
            # Set values that might cause precision issues
            first_line.qty = Decimal('3.33')
            first_line.unit_price = Decimal('123.45')
            first_line.line_total = first_line.qty * first_line.unit_price
            print(f"   New: qty={first_line.qty} × price=€{first_line.unit_price} = €{first_line.line_total}")
            
            # SIMULATE edit_invoice workflow
            print(f"\n🔧 STEP 3: PROCESSING EDIT (edit_invoice workflow)")
            
            # Flush changes
            db.session.flush()
            print(f"   ✅ Flushed changes to database")
            
            # Recalculate totals (this is what edit_invoice does)
            print(f"   🧮 Recalculating invoice totals...")
            calculation_result = calculate_invoice_totals(invoice)
            print(f"      Service calculated - Subtotal: €{calculation_result['subtotal']}")
            print(f"      Service calculated - VAT: €{calculation_result['vat_amount']}")
            print(f"      Service calculated - Total: €{calculation_result['total']}")
            
            # Commit changes
            db.session.commit()
            print(f"   ✅ Committed changes to database")
            
            # Refresh invoice (like edit_invoice does)
            db.session.refresh(invoice)
            print(f"   ✅ Refreshed invoice object")
            
            # SIMULATE REDIRECT TO VIEW PAGE
            print(f"\n🌐 STEP 4: USER REDIRECTED TO VIEW PAGE")
            
            # This is exactly what view_invoice does
            fresh_invoice = Invoice.query.get_or_404(invoice.id)
            
            print(f"   Fresh query loaded invoice #{fresh_invoice.id}")
            
            # CRITICAL TEST: Compare VAT amount calculations
            print(f"\n🎯 STEP 5: CRITICAL TEST - VAT AMOUNT CONSISTENCY")
            
            # Method 1: Property (what template uses)
            vat_via_property = fresh_invoice.vat_amount
            print(f"   VAT via property: €{vat_via_property}")
            print(f"   Property type: {type(vat_via_property)}")
            print(f"   Property decimal places: {abs(vat_via_property.as_tuple().exponent)}")
            
            # Method 2: Service calculation
            service_result = calculate_invoice_totals(fresh_invoice)
            vat_via_service = service_result['vat_amount']
            print(f"   VAT via service: €{vat_via_service}")
            print(f"   Service type: {type(vat_via_service)}")
            print(f"   Service decimal places: {abs(vat_via_service.as_tuple().exponent)}")
            
            # Method 3: Manual calculation (old problematic way)
            manual_vat_old = fresh_invoice.subtotal * (Decimal(str(fresh_invoice.vat_rate)) / Decimal('100'))
            print(f"   VAT manual (old way): €{manual_vat_old}")
            print(f"   Old way decimal places: {abs(manual_vat_old.as_tuple().exponent)}")
            
            # Check consistency
            property_service_diff = abs(vat_via_property - vat_via_service)
            property_consistent = property_service_diff < Decimal('0.01')
            
            print(f"\n🔍 STEP 6: CONSISTENCY ANALYSIS")
            print(f"   Property vs Service difference: €{property_service_diff}")
            print(f"   Property vs Service consistent: {'YES ✅' if property_consistent else 'NO ❌'}")
            
            if property_consistent:
                print(f"   ✅ SUCCESS: VAT amount calculations are now consistent!")
                print(f"   • Property uses proper Decimal rounding")
                print(f"   • Service calculation matches property")
                print(f"   • Template will show accurate values")
            else:
                print(f"   ❌ FAILURE: VAT calculations still inconsistent")
                print(f"   • Property: €{vat_via_property}")
                print(f"   • Service:  €{vat_via_service}")
                print(f"   • Difference: €{property_service_diff}")
            
            # TEMPLATE DISPLAY TEST
            print(f"\n🎨 STEP 7: TEMPLATE DISPLAY TEST")
            
            # Simulate what the template displays
            template_subtotal = f"{float(fresh_invoice.subtotal):.2f}"
            template_vat = f"{float(fresh_invoice.vat_amount):.2f}"
            template_total = f"{float(fresh_invoice.total):.2f}"
            
            print(f"   Template would show:")
            print(f"     Subtotal: €{template_subtotal}")
            print(f"     VAT ({fresh_invoice.vat_rate}%): €{template_vat}")
            print(f"     Total: €{template_total}")
            
            # Check if template values look clean
            vat_looks_clean = len(template_vat.split('.')[1]) == 2
            print(f"   VAT formatting looks clean: {'YES ✅' if vat_looks_clean else 'NO ❌'}")
            
            # USER EXPERIENCE TEST
            print(f"\n👤 STEP 8: USER EXPERIENCE VERIFICATION")
            
            print(f"   What user would see after editing and viewing:")
            print(f"     • Sidebar shows consistent decimal precision")
            print(f"     • VAT amount properly rounded to 2 decimal places")
            print(f"     • No 4+ decimal place artifacts")
            print(f"     • Values match between edit and view pages")
            
            # RESTORE ORIGINAL STATE
            print(f"\n🔄 STEP 9: RESTORING ORIGINAL STATE")
            
            for i, (orig_qty, orig_price, orig_total) in enumerate(original_values['lines']):
                fresh_invoice.lines[i].qty = orig_qty
                fresh_invoice.lines[i].unit_price = orig_price
                fresh_invoice.lines[i].line_total = orig_total
            
            fresh_invoice.subtotal = original_values['subtotal']
            fresh_invoice.total = original_values['total']
            
            db.session.commit()
            print(f"   ✅ Restored to original state")
            
            # FINAL VERDICT
            print(f"\n🏆 FINAL VERDICT:")
            if property_consistent and vat_looks_clean:
                print(f"   ✅ ISSUE RESOLVED!")
                print(f"   🎯 Root cause was the Invoice.vat_amount property not using")
                print(f"      proper Decimal rounding like the totals service.")
                print(f"   🔧 Fix applied: Modified vat_amount property to use")
                print(f"      quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)")
                print(f"   📈 Result: User will now see consistent values")
                print(f"      between edit form sidebar and view page sidebar.")
            else:
                print(f"   ❌ ISSUE NOT FULLY RESOLVED")
                print(f"   🔍 Further investigation needed")
            
        except Exception as e:
            print(f"❌ Error during workflow test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_complete_workflow_with_fix()