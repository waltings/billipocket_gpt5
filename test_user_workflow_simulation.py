#!/usr/bin/env python3
"""
Simulate the exact user workflow described in the issue to identify the problem.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine, Client
from app.services.totals import calculate_invoice_totals
from decimal import Decimal
from datetime import date
import traceback

def create_test_invoice():
    """Create a test invoice for the workflow simulation."""
    
    # Find or create a client
    client = Client.query.first()
    if not client:
        client = Client(
            name="Test Client",
            email="test@example.com",
            phone="+372 12345678"
        )
        db.session.add(client)
        db.session.flush()
    
    # Create a test invoice
    invoice = Invoice(
        number="TEST-001",
        client_id=client.id,
        date=date.today(),
        due_date=date.today(),
        vat_rate=24,
        status='maksmata'
    )
    
    db.session.add(invoice)
    db.session.flush()
    
    # Add some test lines
    line1 = InvoiceLine(
        invoice_id=invoice.id,
        description="Test Service 1",
        qty=Decimal('1.00'),
        unit_price=Decimal('100.00'),
        line_total=Decimal('100.00')
    )
    
    line2 = InvoiceLine(
        invoice_id=invoice.id,
        description="Test Service 2", 
        qty=Decimal('2.00'),
        unit_price=Decimal('50.00'),
        line_total=Decimal('100.00')
    )
    
    db.session.add(line1)
    db.session.add(line2)
    db.session.flush()
    
    # Calculate totals
    calculate_invoice_totals(invoice)
    db.session.commit()
    
    return invoice

def simulate_user_workflow():
    """Simulate the exact workflow the user described."""
    print("=== SIMULATING USER WORKFLOW ===\n")
    print("User workflow:")
    print("1. Added new invoice")
    print("2. Clicked 'Muuda arvet' (Edit invoice)")
    print("3. Changed line amounts - real-time calculations work correctly") 
    print("4. Clicked 'Uuenda arvet' (Update invoice)")
    print("5. Redirected to view page")
    print("6. PROBLEM: View page sidebar does NOT show updated subtotal and total")
    print()
    
    app = create_app()
    
    with app.app_context():
        try:
            # STEP 1: Create new invoice (simulating user adding new invoice)
            print("1️⃣ CREATING NEW INVOICE...")
            invoice = create_test_invoice()
            print(f"   ✅ Created invoice #{invoice.id}: {invoice.number}")
            print(f"   Initial totals: Subtotal=€{invoice.subtotal}, Total=€{invoice.total}")
            
            # STEP 2: Load edit page (simulating clicking "Muuda arvet")
            print(f"\n2️⃣ LOADING EDIT PAGE...")
            edit_invoice = Invoice.query.get_or_404(invoice.id)
            print(f"   ✅ Loaded for editing: {edit_invoice.number}")
            print(f"   Edit page shows: Subtotal=€{edit_invoice.subtotal}, Total=€{edit_invoice.total}")
            print(f"   Lines: {len(edit_invoice.lines)}")
            for i, line in enumerate(edit_invoice.lines):
                print(f"     Line {i+1}: {line.description} - €{line.unit_price} x {line.qty} = €{line.line_total}")
            
            # STEP 3: Simulate user changing line amounts (user types new values)
            print(f"\n3️⃣ USER CHANGES LINE AMOUNTS...")
            print(f"   User changes Line 1 price: €100.00 → €150.00")
            print(f"   User changes Line 2 quantity: 2 → 3")
            
            # Simulate what the JavaScript real-time calculation would show
            print(f"\n   📱 REAL-TIME CALCULATION (JavaScript in browser):")
            line1_new_total = 1.0 * 150.0  # JavaScript floating point
            line2_new_total = 3.0 * 50.0   # JavaScript floating point
            js_subtotal = line1_new_total + line2_new_total
            js_vat = js_subtotal * 0.24
            js_total = js_subtotal + js_vat
            
            print(f"     Line 1: 1 × €150.00 = €{line1_new_total}")
            print(f"     Line 2: 3 × €50.00 = €{line2_new_total}")
            print(f"     Subtotal: €{js_subtotal}")
            print(f"     VAT (24%): €{js_vat}")
            print(f"     Total: €{js_total}")
            print(f"   ✅ User sees these values in the sidebar during editing")
            
            # STEP 4: Simulate form submission (clicking "Uuenda arvet")
            print(f"\n4️⃣ USER CLICKS 'UUENDA ARVET' (Update invoice)...")
            
            # This simulates what edit_invoice POST does:
            
            # Update line data (like edit_invoice does in lines 591-594)
            line1 = edit_invoice.lines[0]
            line2 = edit_invoice.lines[1]
            
            line1.unit_price = Decimal('150.00')
            line1.line_total = line1.qty * line1.unit_price  # Decimal calculation
            
            line2.qty = Decimal('3.00')
            line2.line_total = line2.qty * line2.unit_price  # Decimal calculation
            
            print(f"   Updated Line 1: {line1.qty} × €{line1.unit_price} = €{line1.line_total}")
            print(f"   Updated Line 2: {line2.qty} × €{line2.unit_price} = €{line2.line_total}")
            
            # Flush changes (like edit_invoice does on line 620)
            db.session.flush()
            
            # Recalculate totals (like edit_invoice does on line 623)
            print(f"   🧮 SERVER CALCULATION (Python/Decimal):")
            server_result = calculate_invoice_totals(edit_invoice)
            print(f"     Subtotal: €{server_result['subtotal']}")
            print(f"     VAT: €{server_result['vat_amount']}")
            print(f"     Total: €{server_result['total']}")
            
            # Commit (like edit_invoice does on line 626)
            db.session.commit()
            
            # Refresh (like edit_invoice does on line 630)
            db.session.refresh(edit_invoice)
            print(f"   ✅ Changes saved to database")
            
            # STEP 5: Simulate redirect to view page
            print(f"\n5️⃣ REDIRECTING TO VIEW PAGE...")
            print(f"   🌐 Browser redirects to: /invoices/{invoice.id}")
            
            # This is what view_invoice does: Invoice.query.get_or_404(invoice_id)
            view_invoice = Invoice.query.get_or_404(invoice.id)
            
            print(f"\n6️⃣ VIEW PAGE LOADS...")
            print(f"   📄 view_invoice loads fresh data from database")
            print(f"   View page sidebar shows:")
            print(f"     Subtotal: €{view_invoice.subtotal}")
            print(f"     VAT (24%): €{view_invoice.vat_amount}")
            print(f"     Total: €{view_invoice.total}")
            
            # STEP 6: Compare what user expects vs what they see
            print(f"\n🔍 ISSUE ANALYSIS:")
            print(f"   What user SAW during editing (JS calculation):")
            print(f"     Subtotal: €{js_subtotal:.2f}")
            print(f"     VAT: €{js_vat:.2f}")
            print(f"     Total: €{js_total:.2f}")
            
            print(f"   What user SEES on view page (DB values):")
            print(f"     Subtotal: €{view_invoice.subtotal}")
            print(f"     VAT: €{view_invoice.vat_amount}")
            print(f"     Total: €{view_invoice.total}")
            
            # Check for discrepancy
            subtotal_diff = abs(float(view_invoice.subtotal) - js_subtotal)
            total_diff = abs(float(view_invoice.total) - js_total)
            
            if subtotal_diff > 0.01 or total_diff > 0.01:
                print(f"   ❌ VALUES DON'T MATCH!")
                print(f"     Subtotal difference: €{subtotal_diff:.6f}")
                print(f"     Total difference: €{total_diff:.6f}")
                print(f"   🎯 ROOT CAUSE: User expectation mismatch!")
                print(f"      - User expects to see the JavaScript-calculated values")
                print(f"      - But view page shows server-calculated (more accurate) values")
            else:
                print(f"   ✅ Values match - no discrepancy")
                print(f"   🤔 Issue might be elsewhere...")
            
            # Test if the issue is related to decimal formatting
            print(f"\n🎨 TEMPLATE FORMATTING TEST:")
            print(f"   Template format {{ \"%.2f\"|format(invoice.subtotal) }}€ = €{float(view_invoice.subtotal):.2f}")
            print(f"   Template format {{ \"%.2f\"|format(invoice.total) }}€ = €{float(view_invoice.total):.2f}")
            
            # Clean up
            print(f"\n🧹 CLEANING UP...")
            db.session.delete(invoice)
            db.session.commit()
            print(f"   ✅ Test invoice deleted")
            
        except Exception as e:
            print(f"❌ Error during simulation: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    simulate_user_workflow()