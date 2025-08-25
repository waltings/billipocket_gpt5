#!/usr/bin/env python3
"""
Test script to verify the sidebar summary update fix after invoice editing.

This test verifies that:
1. After editing invoice line items and changing amounts
2. The sidebar totals (Vahesumma, KM, KOKKU) are updated correctly
3. The computed property invoice.vat_amount reflects the new values
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, Client, InvoiceLine, VatRate
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
from datetime import date, timedelta


def test_sidebar_update_fix():
    """Test that sidebar totals update correctly after invoice editing."""
    print("🧪 Testing sidebar summary update fix...")
    
    app = create_app()
    
    with app.app_context():
        # Find or create a test invoice
        invoice = Invoice.query.first()
        if not invoice:
            # Create test data if needed
            client = Client.query.first()
            if not client:
                client = Client(
                    name="Test Client",
                    email="test@example.com"
                )
                db.session.add(client)
                db.session.flush()
            
            invoice = Invoice(
                number="TEST-001",
                client_id=client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate=24,
                status='maksmata'
            )
            db.session.add(invoice)
            db.session.flush()
            
            # Add a test line
            line = InvoiceLine(
                invoice_id=invoice.id,
                description="Test service",
                qty=1,
                unit_price=100.00,
                line_total=100.00
            )
            db.session.add(line)
            db.session.flush()
            
            calculate_invoice_totals(invoice)
            db.session.commit()
        
        print(f"📋 Using invoice: {invoice.number} (ID: {invoice.id})")
        
        # Test 1: Record original values
        print("\n🔍 Step 1: Recording original values...")
        original_subtotal = float(invoice.subtotal)
        original_vat_amount = float(invoice.vat_amount)
        original_total = float(invoice.total)
        
        print(f"   Original subtotal: €{original_subtotal:.2f}")
        print(f"   Original VAT amount: €{original_vat_amount:.2f}")
        print(f"   Original total: €{original_total:.2f}")
        
        # Test 2: Modify line amounts to simulate editing
        print("\n✏️  Step 2: Simulating invoice line edit...")
        if invoice.lines:
            line = invoice.lines[0]
            old_amount = float(line.line_total)
            new_amount = old_amount + 50.00  # Add €50
            
            print(f"   Changing line from €{old_amount:.2f} to €{new_amount:.2f}")
            
            line.unit_price = new_amount
            line.line_total = new_amount
            
            # Recalculate totals (this is what happens in the route)
            calculate_invoice_totals(invoice)
            
            # Commit and refresh (the fix we just added)
            db.session.commit()
            db.session.refresh(invoice)  # This is the critical fix
        
        # Test 3: Verify updated values
        print("\n✅ Step 3: Verifying updated values...")
        new_subtotal = float(invoice.subtotal)
        new_vat_amount = float(invoice.vat_amount)
        new_total = float(invoice.total)
        
        print(f"   New subtotal: €{new_subtotal:.2f}")
        print(f"   New VAT amount: €{new_vat_amount:.2f}")
        print(f"   New total: €{new_total:.2f}")
        
        # Test 4: Validate calculations
        print("\n🔢 Step 4: Validating calculations...")
        expected_vat = new_subtotal * 0.24  # 24% VAT
        expected_total = new_subtotal + expected_vat
        
        vat_correct = abs(new_vat_amount - expected_vat) < 0.01
        total_correct = abs(new_total - expected_total) < 0.01
        
        print(f"   Expected VAT: €{expected_vat:.2f}, Actual: €{new_vat_amount:.2f} {'✅' if vat_correct else '❌'}")
        print(f"   Expected total: €{expected_total:.2f}, Actual: €{new_total:.2f} {'✅' if total_correct else '❌'}")
        
        # Test 5: Test computed property directly
        print("\n🧮 Step 5: Testing computed property...")
        computed_vat = float(invoice.vat_amount)
        property_correct = abs(computed_vat - expected_vat) < 0.01
        
        print(f"   invoice.vat_amount property: €{computed_vat:.2f} {'✅' if property_correct else '❌'}")
        
        # Final result
        print(f"\n🎯 Final Result:")
        if vat_correct and total_correct and property_correct:
            print("   ✅ SUCCESS: Sidebar update fix is working correctly!")
            print("   ✅ VAT amount computed property reflects updated values")
            print("   ✅ Sidebar totals will now display correct values after editing")
            return True
        else:
            print("   ❌ FAILURE: Issues detected with the fix")
            if not vat_correct:
                print("   ❌ VAT calculation is incorrect")
            if not total_correct:
                print("   ❌ Total calculation is incorrect")
            if not property_correct:
                print("   ❌ Computed property is not returning updated values")
            return False


def test_without_refresh():
    """Test what happens WITHOUT the refresh call to demonstrate the issue."""
    print("\n🔬 Demonstrating the original issue (without refresh)...")
    
    app = create_app()
    
    with app.app_context():
        # Get a test invoice
        invoice = Invoice.query.first()
        if not invoice:
            print("   No test invoice available")
            return
        
        print(f"📋 Using invoice: {invoice.number}")
        
        # Record original values
        print("\n🔍 Recording original values...")
        original_subtotal = float(invoice.subtotal)
        original_vat_amount = float(invoice.vat_amount)
        
        print(f"   Subtotal: €{original_subtotal:.2f}")
        print(f"   VAT amount: €{original_vat_amount:.2f}")
        
        # Simulate editing without refresh
        if invoice.lines:
            line = invoice.lines[0]
            line.line_total = float(line.line_total) + 25.00
            
            # Recalculate totals
            calculate_invoice_totals(invoice)
            
            # Commit but DON'T refresh
            db.session.commit()
            # db.session.refresh(invoice)  # This line is commented out
        
        # Check values
        print("\n🔍 After commit (without refresh)...")
        new_subtotal = float(invoice.subtotal)
        new_vat_amount = float(invoice.vat_amount)
        
        print(f"   Subtotal: €{new_subtotal:.2f}")
        print(f"   VAT amount: €{new_vat_amount:.2f}")
        
        # The issue: vat_amount might still be calculated from cached subtotal
        expected_vat = new_subtotal * 0.24
        actual_vat = new_vat_amount
        
        if abs(actual_vat - expected_vat) > 0.01:
            print(f"   ❌ ISSUE DETECTED: VAT amount ({actual_vat:.2f}) doesn't match expected ({expected_vat:.2f})")
            print("   💡 This is why we need db.session.refresh(invoice)")
        else:
            print(f"   ✅ Values appear correct (this can vary depending on SQLAlchemy behavior)")


if __name__ == '__main__':
    print("🚀 Testing invoice sidebar update fix...\n")
    
    # Test the fix
    success = test_sidebar_update_fix()
    
    # Demonstrate original issue
    test_without_refresh()
    
    print(f"\n{'='*60}")
    if success:
        print("🎉 CONCLUSION: The fix is working correctly!")
        print("   The sidebar totals will now update properly after invoice editing.")
    else:
        print("⚠️  CONCLUSION: The fix needs additional work.")
    
    print("="*60)