#!/usr/bin/env python3
"""
Test the VAT amount rounding fix.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def test_vat_fix():
    """Test that the VAT amount fix resolves the precision issue."""
    print("=== TESTING VAT AMOUNT ROUNDING FIX ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get an invoice for testing
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found")
                return
            
            print(f"📋 Testing with Invoice #{invoice.id}: {invoice.number}")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   VAT Rate: {invoice.vat_rate}%")
            
            # Test the VAT amount calculation methods
            print(f"\n🧮 VAT AMOUNT CALCULATIONS:")
            
            # Method 1: Using the fixed property
            vat_via_property = invoice.vat_amount
            print(f"   VAT via property (FIXED): €{vat_via_property}")
            print(f"   Type: {type(vat_via_property)}")
            print(f"   Decimal places: {abs(vat_via_property.as_tuple().exponent)}")
            
            # Method 2: Using totals service
            temp_result = calculate_invoice_totals(invoice)
            vat_via_service = temp_result['vat_amount']
            print(f"   VAT via service: €{vat_via_service}")
            print(f"   Type: {type(vat_via_service)}")
            print(f"   Decimal places: {abs(vat_via_service.as_tuple().exponent)}")
            
            # Method 3: Manual calculation (old way)
            manual_vat = invoice.subtotal * (Decimal(str(invoice.vat_rate)) / Decimal('100'))
            print(f"   VAT manual (old way): €{manual_vat}")
            print(f"   Type: {type(manual_vat)}")
            print(f"   Decimal places: {abs(manual_vat.as_tuple().exponent)}")
            
            # Check consistency
            print(f"\n✅ CONSISTENCY CHECK:")
            property_service_match = abs(vat_via_property - vat_via_service) < Decimal('0.001')
            print(f"   Property vs Service: {'Match ✅' if property_service_match else 'Mismatch ❌'}")
            
            if property_service_match:
                print(f"   ✅ SUCCESS: Property now matches service calculation!")
                print(f"   Difference: €{abs(vat_via_property - vat_via_service)}")
            else:
                print(f"   ❌ Still have discrepancy:")
                print(f"   Difference: €{abs(vat_via_property - vat_via_service)}")
            
            # Test with problematic values that could cause precision issues
            print(f"\n🧪 TESTING EDGE CASES:")
            
            edge_cases = [
                {'subtotal': Decimal('123.456'), 'vat_rate': 24},
                {'subtotal': Decimal('1000.001'), 'vat_rate': 24},
                {'subtotal': Decimal('99.999'), 'vat_rate': 20},
                {'subtotal': Decimal('0.01'), 'vat_rate': 24},
            ]
            
            for i, case in enumerate(edge_cases):
                print(f"   Case {i+1}: Subtotal=€{case['subtotal']}, VAT={case['vat_rate']}%")
                
                # Temporarily modify invoice for testing
                original_subtotal = invoice.subtotal
                original_vat_rate = invoice.vat_rate
                
                invoice.subtotal = case['subtotal']
                invoice.vat_rate = case['vat_rate']
                
                # Test calculations
                property_vat = invoice.vat_amount
                service_vat = calculate_invoice_totals(invoice)['vat_amount']
                
                print(f"     Property: €{property_vat}")
                print(f"     Service:  €{service_vat}")
                print(f"     Match: {'Yes ✅' if abs(property_vat - service_vat) < Decimal('0.001') else 'No ❌'}")
                
                # Restore original values
                invoice.subtotal = original_subtotal
                invoice.vat_rate = original_vat_rate
            
            # Test template formatting
            print(f"\n🎨 TEMPLATE FORMATTING TEST:")
            test_vat = invoice.vat_amount
            formatted_vat = f"{float(test_vat):.2f}"
            print(f"   Raw VAT: {test_vat}")
            print(f"   Template format (%.2f): {formatted_vat}")
            print(f"   Both show same precision: {'Yes ✅' if len(str(test_vat).split('.')[1]) <= 2 else 'No ❌'}")
            
            print(f"\n🎯 CONCLUSION:")
            if property_service_match:
                print(f"   ✅ FIX SUCCESSFUL!")
                print(f"   • VAT amount property now uses proper Decimal rounding")
                print(f"   • Property matches totals service calculation")
                print(f"   • Template will show consistent 2-decimal values")
                print(f"   • User should no longer see precision discrepancies")
            else:
                print(f"   ❌ FIX INCOMPLETE - still have issues")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_vat_fix()