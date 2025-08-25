#!/usr/bin/env python3
"""
Test to compare JavaScript and Python calculation methods to identify discrepancies.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
import traceback

def simulate_javascript_calculation(invoice):
    """Simulate the JavaScript calculation method from invoice_form.html updateTotals()."""
    
    # Simulate JavaScript: let subtotal = 0;
    subtotal = 0.0  # JavaScript uses floating point
    
    # Simulate: document.querySelectorAll('.invoice-line:not(.marked-for-deletion)').forEach(line => {
    for line in invoice.lines:
        # Simulate: const qty = parseFloat(line.querySelector('.line-qty')?.value) || 0;
        qty = float(line.qty) if line.qty else 0.0
        
        # Simulate: const price = parseFloat(line.querySelector('.line-price')?.value) || 0;
        price = float(line.unit_price) if line.unit_price else 0.0
        
        # Simulate: const lineTotal = qty * price;
        line_total = qty * price
        
        # Simulate: subtotal += lineTotal;
        subtotal += line_total
        
        print(f"  JS Line: qty={qty} * price={price} = {line_total} (subtotal so far: {subtotal})")
    
    # Simulate: const vatRate = vatRateMap[vatRateId] || 24;
    vat_rate = float(invoice.vat_rate) if invoice.vat_rate else 24.0
    
    # Simulate: const vatAmount = subtotal * (vatRate / 100);
    vat_amount = subtotal * (vat_rate / 100)
    
    # Simulate: const total = subtotal + vatAmount;
    total = subtotal + vat_amount
    
    return {
        'subtotal': subtotal,
        'vat_amount': vat_amount,
        'total': total
    }

def test_calculation_methods():
    """Test different calculation methods to find discrepancies."""
    print("=== COMPARING JAVASCRIPT vs PYTHON CALCULATIONS ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get an invoice with multiple lines for testing
            invoice = Invoice.query.first()
            if not invoice or len(invoice.lines) < 2:
                print("❌ Need an invoice with at least 2 lines for testing")
                return
            
            print(f"📋 Testing with Invoice #{invoice.id}: {invoice.number}")
            print(f"   Lines: {len(invoice.lines)}")
            
            # Show current database values
            print(f"\n💾 CURRENT DATABASE VALUES:")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   VAT Amount: €{invoice.vat_amount}")
            print(f"   Total: €{invoice.total}")
            
            # Method 1: Python service calculation (what edit_invoice uses)
            print(f"\n🐍 PYTHON SERVICE CALCULATION:")
            python_result = calculate_invoice_totals(invoice)
            print(f"   Subtotal: €{python_result['subtotal']}")
            print(f"   VAT Amount: €{python_result['vat_amount']}")
            print(f"   Total: €{python_result['total']}")
            
            # Method 2: JavaScript simulation (what user sees in edit form)
            print(f"\n🟨 JAVASCRIPT SIMULATION:")
            js_result = simulate_javascript_calculation(invoice)
            print(f"   Subtotal: €{js_result['subtotal']}")
            print(f"   VAT Amount: €{js_result['vat_amount']}")
            print(f"   Total: €{js_result['total']}")
            
            # Method 3: Manual Decimal calculation
            print(f"\n🔢 MANUAL DECIMAL CALCULATION:")
            manual_subtotal = sum(Decimal(str(line.line_total)) for line in invoice.lines)
            manual_vat = manual_subtotal * (Decimal(str(invoice.vat_rate)) / Decimal('100'))
            manual_total = manual_subtotal + manual_vat
            print(f"   Subtotal: €{manual_subtotal}")
            print(f"   VAT Amount: €{manual_vat}")
            print(f"   Total: €{manual_total}")
            
            # Check for discrepancies
            print(f"\n🔍 DISCREPANCY ANALYSIS:")
            
            # Check Python vs JavaScript
            py_js_match = (
                abs(float(python_result['subtotal']) - js_result['subtotal']) < 0.01 and
                abs(float(python_result['vat_amount']) - js_result['vat_amount']) < 0.01 and
                abs(float(python_result['total']) - js_result['total']) < 0.01
            )
            
            print(f"   Python vs JavaScript: {'Match ✅' if py_js_match else 'Discrepancy ❌'}")
            
            if not py_js_match:
                print(f"     Subtotal diff: {abs(float(python_result['subtotal']) - js_result['subtotal']):.6f}")
                print(f"     VAT diff: {abs(float(python_result['vat_amount']) - js_result['vat_amount']):.6f}")
                print(f"     Total diff: {abs(float(python_result['total']) - js_result['total']):.6f}")
            
            # Check Database vs Python
            db_py_match = (
                abs(float(invoice.subtotal) - float(python_result['subtotal'])) < 0.01 and
                abs(float(invoice.total) - float(python_result['total'])) < 0.01
            )
            
            print(f"   Database vs Python: {'Match ✅' if db_py_match else 'Discrepancy ❌'}")
            
            # Check Database vs JavaScript
            db_js_match = (
                abs(float(invoice.subtotal) - js_result['subtotal']) < 0.01 and
                abs(float(invoice.total) - js_result['total']) < 0.01
            )
            
            print(f"   Database vs JavaScript: {'Match ✅' if db_js_match else 'Discrepancy ❌'}")
            
            # Identify the root cause
            print(f"\n🎯 ROOT CAUSE ANALYSIS:")
            
            if py_js_match and db_py_match and db_js_match:
                print("   ✅ All calculation methods match perfectly")
                print("   ➡️ Issue might be:")
                print("      - Browser caching")
                print("      - User perception (expecting different values)")
                print("      - Timing issue in the workflow")
                
            elif not db_py_match:
                print("   ❌ Database values don't match Python calculation")
                print("   ➡️ Problem: Database totals not being updated correctly")
                
            elif not py_js_match:
                print("   ❌ Python and JavaScript calculations differ")
                print("   ➡️ Problem: Inconsistent calculation logic")
                
            elif not db_js_match:
                print("   ❌ Database and JavaScript values differ")
                print("   ➡️ Problem: User sees different values in edit vs view")
                
            # Test edge case: Modify line values and see behavior
            print(f"\n🧪 TESTING EDGE CASE: Modifying line with decimal precision")
            
            # Change a line to a value that might cause precision issues
            original_price = invoice.lines[0].unit_price
            original_line_total = invoice.lines[0].line_total
            
            # Set a price that could cause floating point precision issues
            test_price = Decimal('123.456')  # 3 decimal places
            invoice.lines[0].unit_price = test_price
            invoice.lines[0].line_total = invoice.lines[0].qty * test_price
            
            print(f"   Modified line: qty={invoice.lines[0].qty} * price=€{test_price} = €{invoice.lines[0].line_total}")
            
            # Test calculations with the modified values
            edge_python = calculate_invoice_totals(invoice)
            edge_js = simulate_javascript_calculation(invoice)
            
            print(f"   Python result: €{edge_python['total']}")
            print(f"   JavaScript result: €{edge_js['total']:.2f}")
            print(f"   Difference: {abs(float(edge_python['total']) - edge_js['total']):.6f}")
            
            # Restore original values
            invoice.lines[0].unit_price = original_price
            invoice.lines[0].line_total = original_line_total
            calculate_invoice_totals(invoice)
            
            print(f"   ✅ Restored original values")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_calculation_methods()