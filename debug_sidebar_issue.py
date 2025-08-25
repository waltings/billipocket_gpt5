#!/usr/bin/env python3
"""
Debug script to investigate the sidebar issue where view_invoice shows stale totals after editing.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db, Invoice, InvoiceLine, Client
from app.services.totals import calculate_invoice_totals
import traceback

def debug_invoice_view_issue():
    """Debug the specific issue where view_invoice shows stale totals."""
    print("=== DEBUG: Invoice View Sidebar Issue ===\n")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Find an existing invoice or create one for testing
            invoice = Invoice.query.first()
            if not invoice:
                print("❌ No invoices found in database. Please create an invoice first.")
                return
            
            print(f"📋 Testing with Invoice #{invoice.id}: {invoice.number}")
            print(f"   Client: {invoice.client.name}")
            print(f"   Lines: {len(invoice.lines)}")
            
            # Show current totals from database
            print(f"\n💾 DATABASE VALUES:")
            print(f"   Subtotal: €{invoice.subtotal}")
            print(f"   VAT Amount: €{invoice.vat_amount}")
            print(f"   Total: €{invoice.total}")
            
            # Show totals as calculated from lines
            print(f"\n🧮 CALCULATED VALUES (from lines):")
            from decimal import Decimal
            calculated_subtotal = sum(Decimal(str(line.line_total)) for line in invoice.lines)
            calculated_vat = calculated_subtotal * (Decimal(str(invoice.vat_rate)) / Decimal('100'))
            calculated_total = calculated_subtotal + calculated_vat
            
            print(f"   Subtotal: €{calculated_subtotal}")
            print(f"   VAT Amount: €{calculated_vat}")
            print(f"   Total: €{calculated_total}")
            
            # Check if values match
            db_matches_calc = (
                abs(float(invoice.subtotal) - float(calculated_subtotal)) < 0.01 and
                abs(float(invoice.total) - float(calculated_total)) < 0.01
            )
            
            print(f"\n✅ Values match: {'Yes' if db_matches_calc else 'No'}")
            
            if not db_matches_calc:
                print("❌ ISSUE FOUND: Database values don't match calculated values!")
                print("   This suggests the invoice totals in DB are not updated correctly.")
                
                # Try recalculating and see if it fixes the issue
                print("\n🔧 Recalculating totals...")
                calculate_invoice_totals(invoice)
                db.session.commit()
                
                # Refresh invoice to get updated values
                db.session.refresh(invoice)
                
                print(f"\n💾 UPDATED DATABASE VALUES:")
                print(f"   Subtotal: €{invoice.subtotal}")
                print(f"   VAT Amount: €{invoice.vat_amount}")
                print(f"   Total: €{invoice.total}")
            
            # Test the view_invoice route behavior
            print(f"\n🌐 TESTING view_invoice ROUTE...")
            
            # Simulate what view_invoice does
            fresh_invoice = Invoice.query.get_or_404(invoice.id)
            print(f"   Fresh query - Subtotal: €{fresh_invoice.subtotal}")
            print(f"   Fresh query - Total: €{fresh_invoice.total}")
            
            # Check if relationships are loaded correctly
            print(f"   Lines loaded: {len(fresh_invoice.lines)}")
            for i, line in enumerate(fresh_invoice.lines):
                print(f"     Line {i+1}: {line.description[:30]}... = €{line.line_total}")
            
            # Test the template data that would be passed
            template_data = {
                'invoice': fresh_invoice,
                'subtotal': fresh_invoice.subtotal,
                'vat_amount': fresh_invoice.vat_amount,
                'total': fresh_invoice.total
            }
            
            print(f"\n🎭 TEMPLATE DATA WOULD SHOW:")
            print(f"   invoice.subtotal: €{template_data['invoice'].subtotal}")
            print(f"   invoice.vat_amount: €{template_data['invoice'].vat_amount}")
            print(f"   invoice.total: €{template_data['invoice'].total}")
            
            # Test session state
            print(f"\n🗂️ SESSION STATE:")
            print(f"   Session dirty: {db.session.dirty}")
            print(f"   Session new: {db.session.new}")
            print(f"   Session identity map: {len(db.session.identity_map)}")
            
        except Exception as e:
            print(f"❌ Error during debug: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    debug_invoice_view_issue()