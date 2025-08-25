"""
Tests for concurrent invoice editing scenarios.

Tests what happens when multiple users try to edit the same invoice
simultaneously and ensures database consistency during concurrent operations.
"""

import pytest
import threading
import time
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models import db, Invoice, InvoiceLine, Client, VatRate
from app.services.totals import calculate_invoice_totals


class TestConcurrentInvoiceEditing:
    """Test concurrent invoice editing scenarios."""
    
    def test_concurrent_basic_field_edits(self, client, app_context, sample_invoice):
        """Test concurrent edits to basic invoice fields."""
        
        def edit_invoice_session1():
            """Session 1: Edit note field."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'note': 'Session 1 edit',
                'lines-0-description': 'Session 1 service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def edit_invoice_session2():
            """Session 2: Edit client_extra_info field."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'client_extra_info': 'Session 2 client info',
                'lines-0-description': 'Session 2 service',
                'lines-0-qty': '2.00',
                'lines-0-unit_price': '150.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute concurrent edits
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(edit_invoice_session1)
            future2 = executor.submit(edit_invoice_session2)
            
            # Wait for both to complete
            result1 = future1.result()
            result2 = future2.result()
        
        # Both requests should succeed
        assert result1 == 200
        assert result2 == 200
        
        # Refresh invoice and verify final state
        db.session.refresh(sample_invoice)
        
        # One of the edits should have won (last writer wins)
        # The database should be in a consistent state
        assert sample_invoice.note in ['Session 1 edit', None]
        assert sample_invoice.client_extra_info in ['Session 2 client info', None]
        
        # Verify line data is consistent
        assert len(sample_invoice.lines) > 0
        line = sample_invoice.lines[0]
        assert line.description in ['Session 1 service', 'Session 2 service']
    
    def test_concurrent_line_modifications(self, client, app_context, sample_invoice):
        """Test concurrent modifications to invoice lines."""
        
        # Ensure invoice has at least one line
        if not sample_invoice.lines:
            line = InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Original line',
                qty=Decimal('1.00'),
                unit_price=Decimal('100.00'),
                line_total=Decimal('100.00')
            )
            db.session.add(line)
            db.session.commit()
        
        original_line_id = sample_invoice.lines[0].id
        
        def modify_line_session1():
            """Session 1: Modify quantity."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-id': str(original_line_id),
                'lines-0-description': 'Concurrent test line',
                'lines-0-qty': '3.00',  # Session 1 quantity
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def modify_line_session2():
            """Session 2: Modify price."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-id': str(original_line_id),
                'lines-0-description': 'Concurrent test line',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '200.00'  # Session 2 price
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute concurrent line modifications
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(modify_line_session1)
            future2 = executor.submit(modify_line_session2)
            
            result1 = future1.result()
            result2 = future2.result()
        
        # Both should succeed
        assert result1 == 200
        assert result2 == 200
        
        # Verify final state is consistent
        db.session.refresh(sample_invoice)
        line = sample_invoice.lines[0]
        
        # Final state should be one of the two valid combinations
        valid_combinations = [
            (Decimal('3.00'), Decimal('100.00')),  # Session 1 won
            (Decimal('1.00'), Decimal('200.00'))   # Session 2 won
        ]
        
        actual_combination = (line.qty, line.unit_price)
        assert actual_combination in valid_combinations
        
        # Line total should be correctly calculated
        expected_total = line.qty * line.unit_price
        assert line.line_total == expected_total
    
    def test_concurrent_vat_rate_changes(self, client, app_context, sample_invoice):
        """Test concurrent VAT rate changes."""
        VatRate.create_default_rates()
        db.session.commit()
        
        vat_rates = VatRate.get_active_rates()
        rate1 = vat_rates[0]  # First rate
        rate2 = vat_rates[1] if len(vat_rates) > 1 else vat_rates[0]  # Second rate
        
        def change_vat_session1():
            """Session 1: Change to rate1."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(rate1.id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'VAT test service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def change_vat_session2():
            """Session 2: Change to rate2."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(rate2.id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'VAT test service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute concurrent VAT changes
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(change_vat_session1)
            future2 = executor.submit(change_vat_session2)
            
            result1 = future1.result()
            result2 = future2.result()
        
        assert result1 == 200
        assert result2 == 200
        
        # Verify final VAT rate is one of the two
        db.session.refresh(sample_invoice)
        assert sample_invoice.vat_rate_id in [rate1.id, rate2.id]
        
        # Verify totals are consistent with the final VAT rate
        sample_invoice.calculate_totals()
        expected_vat_rate = sample_invoice.get_effective_vat_rate()
        expected_vat_amount = sample_invoice.subtotal * (expected_vat_rate / 100)
        
        assert abs(sample_invoice.vat_amount - expected_vat_amount) < Decimal('0.01')
    
    def test_concurrent_line_addition_and_removal(self, client, app_context, sample_invoice):
        """Test concurrent line addition and removal operations."""
        
        # Ensure starting state
        if not sample_invoice.lines:
            line = InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Initial line',
                qty=Decimal('1.00'),
                unit_price=Decimal('50.00'),
                line_total=Decimal('50.00')
            )
            db.session.add(line)
            db.session.commit()
        
        initial_line_count = len(sample_invoice.lines)
        
        def add_lines_session():
            """Session 1: Add multiple lines."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                # Keep original line
                'lines-0-description': 'Original line',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '50.00',
                # Add new lines
                'lines-1-description': 'Added line 1',
                'lines-1-qty': '2.00',
                'lines-1-unit_price': '75.00',
                'lines-2-description': 'Added line 2',
                'lines-2-qty': '1.00',
                'lines-2-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def modify_existing_session():
            """Session 2: Modify existing line only."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                # Only modify the original line
                'lines-0-description': 'Modified original line',
                'lines-0-qty': '3.00',
                'lines-0-unit_price': '60.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(add_lines_session)
            future2 = executor.submit(modify_existing_session)
            
            result1 = future1.result()
            result2 = future2.result()
        
        assert result1 == 200
        assert result2 == 200
        
        # Verify final state
        db.session.refresh(sample_invoice)
        
        # Should have at least the original line
        assert len(sample_invoice.lines) >= 1
        
        # The final state should be consistent
        # Either we have 3 lines (add session won) or 1 line (modify session won)
        final_line_count = len(sample_invoice.lines)
        assert final_line_count in [1, 3]
        
        # Verify totals are correctly calculated
        sample_invoice.calculate_totals()
        calculated_subtotal = sum(line.line_total for line in sample_invoice.lines)
        assert sample_invoice.subtotal == calculated_subtotal


class TestDatabaseConsistencyDuringConcurrentOps:
    """Test database consistency during concurrent operations."""
    
    def test_transaction_isolation_integrity(self, client, app_context, sample_invoice):
        """Test that concurrent transactions maintain database integrity."""
        
        original_total = sample_invoice.total
        
        def heavy_calculation_edit():
            """Simulate heavy calculation during edit."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Heavy calc service',
                'lines-0-qty': '10.00',
                'lines-0-unit_price': '123.45'
            }
            
            # Simulate processing delay
            time.sleep(0.1)
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def quick_status_change():
            """Quick status change during heavy calculation."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': 'saadetud',  # Change status
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Quick change service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '50.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute operations with slight timing overlap
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(heavy_calculation_edit)
            time.sleep(0.05)  # Small delay to create overlap
            future2 = executor.submit(quick_status_change)
            
            result1 = future1.result()
            result2 = future2.result()
        
        assert result1 == 200
        assert result2 == 200
        
        # Verify database is in consistent state
        db.session.refresh(sample_invoice)
        
        # Should have exactly one line (not corrupted)
        assert len(sample_invoice.lines) == 1
        
        # Status should be in valid state
        assert sample_invoice.status in ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
        
        # Totals should be consistent with lines
        sample_invoice.calculate_totals()
        recalculated_total = sample_invoice.subtotal + sample_invoice.vat_amount
        
        assert abs(sample_invoice.total - recalculated_total) < Decimal('0.01')
    
    def test_concurrent_total_recalculations(self, client, app_context, sample_invoice):
        """Test that concurrent total recalculations don't create inconsistencies."""
        
        # Set up invoice with known state
        if sample_invoice.lines:
            for line in sample_invoice.lines:
                db.session.delete(line)
        
        line = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Base line',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        def edit_with_recalculation_1():
            """Edit that triggers recalculation."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Recalc test 1',
                'lines-0-qty': '5.00',
                'lines-0-unit_price': '20.00'  # 100.00 total
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def edit_with_recalculation_2():
            """Another edit that triggers recalculation."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Recalc test 2',
                'lines-0-qty': '2.00',
                'lines-0-unit_price': '50.00'  # 100.00 total
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Execute concurrent recalculations
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(edit_with_recalculation_1)
            future2 = executor.submit(edit_with_recalculation_2)
            
            result1 = future1.result()
            result2 = future2.result()
        
        assert result1 == 200
        assert result2 == 200
        
        # Verify final totals are mathematically correct
        db.session.refresh(sample_invoice)
        line = sample_invoice.lines[0]
        
        # Line total should equal qty * unit_price
        expected_line_total = line.qty * line.unit_price
        assert line.line_total == expected_line_total
        
        # Invoice totals should be consistent
        sample_invoice.calculate_totals()
        assert sample_invoice.subtotal == line.line_total
        
        expected_total = sample_invoice.subtotal + sample_invoice.vat_amount
        assert sample_invoice.total == expected_total
    
    def test_optimistic_locking_behavior(self, client, app_context, sample_invoice):
        """Test behavior with optimistic locking scenarios."""
        
        # Record initial state
        initial_updated_at = sample_invoice.updated_at
        
        def edit_session_with_delay():
            """Edit with artificial delay to simulate slow network."""
            time.sleep(0.2)  # Simulate slow operation
            
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'note': 'Delayed edit',
                'lines-0-description': 'Delayed service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        def quick_edit_session():
            """Quick edit that completes first."""
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'note': 'Quick edit',
                'lines-0-description': 'Quick service',
                'lines-0-qty': '2.00',
                'lines-0-unit_price': '75.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            return response.status_code
        
        # Start delayed edit first, then quick edit
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_delayed = executor.submit(edit_session_with_delay)
            time.sleep(0.1)  # Ensure delayed edit starts first
            future_quick = executor.submit(quick_edit_session)
            
            result_delayed = future_delayed.result()
            result_quick = future_quick.result()
        
        # Both should succeed (last writer wins pattern)
        assert result_delayed == 200
        assert result_quick == 200
        
        # Verify final state
        db.session.refresh(sample_invoice)
        
        # Updated timestamp should be later than initial
        assert sample_invoice.updated_at > initial_updated_at
        
        # Final state should be consistent
        assert sample_invoice.note in ['Delayed edit', 'Quick edit']
        
        # Line data should match the note (indicating which edit won)
        line = sample_invoice.lines[0]
        if sample_invoice.note == 'Delayed edit':
            assert line.description == 'Delayed service'
            assert line.qty == Decimal('1.00')
        elif sample_invoice.note == 'Quick edit':
            assert line.description == 'Quick service'
            assert line.qty == Decimal('2.00')
        
        # Totals should be correct regardless of which edit won
        sample_invoice.calculate_totals()
        expected_total = line.qty * line.unit_price
        assert line.line_total == expected_total