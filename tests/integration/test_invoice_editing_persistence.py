"""
Integration tests for invoice editing data persistence.

Tests that verify changes to invoices are properly saved to the database
and persist correctly across sessions, including real-time updates.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta, datetime
import json

from app.models import db, Invoice, InvoiceLine, Client, VatRate, CompanySettings
from app.services.totals import calculate_invoice_totals, calculate_line_total


class TestInvoiceEditingPersistence:
    """Test invoice editing with database persistence."""
    
    def test_edit_invoice_basic_fields_persistence(self, client, app_context, sample_invoice):
        """Test that basic invoice field edits persist to database."""
        original_number = sample_invoice.number
        original_due_date = sample_invoice.due_date
        
        # Prepare edit data
        new_due_date = original_due_date + timedelta(days=7)
        new_note = "Updated project notes"
        new_client_extra_info = "Additional client information"
        
        form_data = {
            'number': original_number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': new_due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'note': new_note,
            'client_extra_info': new_client_extra_info,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'announcements': 'Updated announcements',
            'lines-0-description': 'Updated service description',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00'
        }
        
        # Submit edit
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh invoice from database
        db.session.refresh(sample_invoice)
        
        # Verify changes persisted
        assert sample_invoice.due_date == new_due_date
        assert sample_invoice.note == new_note
        assert sample_invoice.client_extra_info == new_client_extra_info
        assert sample_invoice.announcements == 'Updated announcements'
        
        # Verify line changes persisted
        assert len(sample_invoice.lines) == 1
        line = sample_invoice.lines[0]
        assert line.description == 'Updated service description'
        assert line.qty == Decimal('2.00')
        assert line.unit_price == Decimal('150.00')
        assert line.line_total == Decimal('300.00')
    
    def test_edit_invoice_vat_rate_change_persistence(self, client, app_context, sample_invoice):
        """Test that VAT rate changes persist and totals are recalculated."""
        # Ensure VAT rates exist
        VatRate.create_default_rates()
        db.session.commit()
        
        # Get different VAT rates
        original_vat_rate = VatRate.get_default_rate()  # 24%
        new_vat_rate = VatRate.query.filter_by(rate=9).first()  # 9%
        
        # Set original VAT rate
        sample_invoice.vat_rate_id = original_vat_rate.id
        sample_invoice.subtotal = Decimal('100.00')
        sample_invoice.calculate_totals()
        db.session.commit()
        
        original_total = sample_invoice.total
        
        # Edit invoice with new VAT rate
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(new_vat_rate.id),  # Change VAT rate
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh and verify changes
        db.session.refresh(sample_invoice)
        
        assert sample_invoice.vat_rate_id == new_vat_rate.id
        assert sample_invoice.get_effective_vat_rate() == Decimal('9')
        
        # Recalculate and verify new total
        sample_invoice.calculate_totals()
        new_total = sample_invoice.total
        
        assert new_total != original_total
        assert new_total == Decimal('109.00')  # 100 + (100 * 0.09)
    
    def test_edit_invoice_add_lines_persistence(self, client, app_context, sample_invoice):
        """Test that adding new lines to an invoice persists correctly."""
        original_line_count = len(sample_invoice.lines)
        
        # Add multiple new lines
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            # Original line
            'lines-0-description': 'Original service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00',
            # New lines
            'lines-1-description': 'Additional service 1',
            'lines-1-qty': '2.00',
            'lines-1-unit_price': '75.00',
            'lines-2-description': 'Additional service 2',
            'lines-2-qty': '0.5',
            'lines-2-unit_price': '200.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh and verify
        db.session.refresh(sample_invoice)
        
        assert len(sample_invoice.lines) == 3
        
        # Verify each line
        lines = sorted(sample_invoice.lines, key=lambda x: x.description)
        
        # Additional service 1
        line1 = next(l for l in lines if 'Additional service 1' in l.description)
        assert line1.qty == Decimal('2.00')
        assert line1.unit_price == Decimal('75.00')
        assert line1.line_total == Decimal('150.00')
        
        # Additional service 2
        line2 = next(l for l in lines if 'Additional service 2' in l.description)
        assert line2.qty == Decimal('0.5')
        assert line2.unit_price == Decimal('200.00')
        assert line2.line_total == Decimal('100.00')
        
        # Verify totals recalculated
        sample_invoice.calculate_totals()
        expected_subtotal = Decimal('100.00') + Decimal('150.00') + Decimal('100.00')
        assert sample_invoice.subtotal == expected_subtotal
    
    def test_edit_invoice_remove_lines_persistence(self, client, app_context):
        """Test that removing lines from an invoice persists correctly."""
        # Create invoice with multiple lines
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-REMOVE-LINES',
            client_id=1,  # Assuming sample client exists
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add multiple lines
        lines_data = [
            {'description': 'Service 1', 'qty': Decimal('1.00'), 'unit_price': Decimal('100.00')},
            {'description': 'Service 2', 'qty': Decimal('2.00'), 'unit_price': Decimal('50.00')},
            {'description': 'Service 3', 'qty': Decimal('1.00'), 'unit_price': Decimal('75.00')}
        ]
        
        for line_data in lines_data:
            line_total = calculate_line_total(line_data['qty'], line_data['unit_price'])
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=line_data['description'],
                qty=line_data['qty'],
                unit_price=line_data['unit_price'],
                line_total=line_total
            )
            db.session.add(line)
        
        db.session.commit()
        
        # Verify initial state
        assert len(invoice.lines) == 3
        
        # Edit to keep only first line
        form_data = {
            'number': invoice.number,
            'client_id': str(invoice.client_id),
            'date': invoice.date.strftime('%Y-%m-%d'),
            'due_date': invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(invoice.vat_rate_id),
            'status': invoice.status,
            'payment_terms': '14 päeva',
            'lines-0-description': 'Service 1',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
            # Only include first line, effectively removing others
        }
        
        response = client.post(f'/invoices/{invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh and verify removal
        db.session.refresh(invoice)
        
        # Should only have one line now
        assert len(invoice.lines) == 1
        assert invoice.lines[0].description == 'Service 1'
        
        # Verify totals recalculated
        invoice.calculate_totals()
        assert invoice.subtotal == Decimal('100.00')
    
    def test_edit_invoice_modify_lines_persistence(self, client, app_context, sample_invoice):
        """Test that modifying existing lines persists correctly."""
        # Ensure sample invoice has at least one line
        if not sample_invoice.lines:
            line = InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Original service',
                qty=Decimal('1.00'),
                unit_price=Decimal('100.00'),
                line_total=Decimal('100.00')
            )
            db.session.add(line)
            db.session.commit()
        
        original_line = sample_invoice.lines[0]
        original_description = original_line.description
        original_qty = original_line.qty
        original_price = original_line.unit_price
        
        # Modify the line
        new_description = 'Modified service description'
        new_qty = Decimal('3.00')
        new_price = Decimal('125.00')
        
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-id': str(original_line.id),  # Include existing line ID
            'lines-0-description': new_description,
            'lines-0-qty': str(new_qty),
            'lines-0-unit_price': str(new_price)
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh and verify changes
        db.session.refresh(sample_invoice)
        db.session.refresh(original_line)
        
        assert original_line.description == new_description
        assert original_line.qty == new_qty
        assert original_line.unit_price == new_price
        assert original_line.line_total == calculate_line_total(new_qty, new_price)
    
    def test_edit_invoice_status_change_persistence(self, client, app_context, sample_invoice):
        """Test that invoice status changes persist correctly."""
        original_status = sample_invoice.status
        new_status = 'saadetud' if original_status == 'mustand' else 'mustand'
        
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': new_status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Refresh and verify status change
        db.session.refresh(sample_invoice)
        assert sample_invoice.status == new_status
    
    def test_edit_invoice_concurrent_session_consistency(self, client, app_context, sample_invoice):
        """Test that edits maintain consistency across concurrent sessions."""
        # Simulate first session edit
        session1_data = {
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
        
        response1 = client.post(f'/invoices/{sample_invoice.id}/edit', 
                              data=session1_data, follow_redirects=True)
        assert response1.status_code == 200
        
        # Refresh and get updated timestamp
        db.session.refresh(sample_invoice)
        first_edit_time = sample_invoice.updated_at
        
        # Wait a moment to ensure timestamp difference
        import time
        time.sleep(0.1)
        
        # Simulate second session edit (should overwrite first)
        session2_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'note': 'Session 2 edit',
            'lines-0-description': 'Session 2 service',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00'
        }
        
        response2 = client.post(f'/invoices/{sample_invoice.id}/edit', 
                              data=session2_data, follow_redirects=True)
        assert response2.status_code == 200
        
        # Verify final state (session 2 should win)
        db.session.refresh(sample_invoice)
        
        assert sample_invoice.note == 'Session 2 edit'
        assert sample_invoice.lines[0].description == 'Session 2 service'
        assert sample_invoice.lines[0].qty == Decimal('2.00')
        assert sample_invoice.lines[0].unit_price == Decimal('150.00')
        assert sample_invoice.updated_at > first_edit_time


class TestRealTimePersistence:
    """Test real-time update persistence scenarios."""
    
    def test_rapid_line_updates_persistence(self, client, app_context, sample_invoice):
        """Test that rapid line updates are all persisted correctly."""
        # Sequence of rapid updates to simulate real-time editing
        updates = [
            {'qty': '1.00', 'price': '100.00'},
            {'qty': '2.00', 'price': '100.00'},
            {'qty': '2.00', 'price': '150.00'},
            {'qty': '3.00', 'price': '150.00'},
            {'qty': '3.00', 'price': '200.00'}
        ]
        
        for i, update in enumerate(updates):
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': f'Update {i+1} service',
                'lines-0-qty': update['qty'],
                'lines-0-unit_price': update['price']
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            assert response.status_code == 200
        
        # Verify final state
        db.session.refresh(sample_invoice)
        final_line = sample_invoice.lines[0]
        
        assert final_line.description == 'Update 5 service'
        assert final_line.qty == Decimal('3.00')
        assert final_line.unit_price == Decimal('200.00')
        assert final_line.line_total == Decimal('600.00')
    
    def test_vat_rate_change_immediate_persistence(self, client, app_context, sample_invoice):
        """Test that VAT rate changes are immediately persisted and calculated."""
        VatRate.create_default_rates()
        db.session.commit()
        
        vat_rates = VatRate.get_active_rates()
        
        # Test changing through all VAT rates
        for vat_rate in vat_rates:
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(vat_rate.id),
                'status': sample_invoice.status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Test service',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                                 data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Immediately verify persistence
            db.session.refresh(sample_invoice)
            assert sample_invoice.vat_rate_id == vat_rate.id
            assert sample_invoice.get_effective_vat_rate() == vat_rate.rate
            
            # Verify calculation is correct
            sample_invoice.calculate_totals()
            expected_total = Decimal('100.00') * (1 + vat_rate.rate / 100)
            assert sample_invoice.total == expected_total
    
    def test_timestamp_updates_on_edit(self, client, app_context, sample_invoice):
        """Test that updated_at timestamp is properly maintained on edits."""
        original_updated_at = sample_invoice.updated_at
        
        # Wait to ensure timestamp difference
        import time
        time.sleep(0.1)
        
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'note': 'Timestamp test edit',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify timestamp was updated
        db.session.refresh(sample_invoice)
        assert sample_invoice.updated_at > original_updated_at


class TestDataIntegrityDuringEdits:
    """Test data integrity during complex edit operations."""
    
    def test_transaction_rollback_on_invalid_data(self, client, app_context, sample_invoice):
        """Test that invalid edits don't partially save data."""
        original_state = {
            'note': sample_invoice.note,
            'line_count': len(sample_invoice.lines),
            'subtotal': sample_invoice.subtotal
        }
        
        # Submit invalid data (missing required fields)
        invalid_form_data = {
            'number': sample_invoice.number,
            'client_id': '',  # Invalid - required field
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'note': 'This should not be saved',
            'lines-0-description': 'Invalid line',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=invalid_form_data, follow_redirects=True)
        
        # Request should succeed but validation should fail
        assert response.status_code == 200
        
        # Verify original data is unchanged
        db.session.refresh(sample_invoice)
        assert sample_invoice.note == original_state['note']
        assert len(sample_invoice.lines) == original_state['line_count']
        assert sample_invoice.subtotal == original_state['subtotal']
    
    def test_complex_edit_atomicity(self, client, app_context, sample_invoice):
        """Test that complex edits (multiple changes) are atomic."""
        # Create complex edit scenario
        VatRate.create_default_rates()
        new_vat_rate = VatRate.query.filter_by(rate=9).first()
        
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': (sample_invoice.due_date + timedelta(days=7)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(new_vat_rate.id),  # Change VAT rate
            'status': 'saadetud',  # Change status
            'payment_terms': '30 päeva',  # Change payment terms
            'note': 'Complex edit test',
            'client_extra_info': 'Updated client info',
            'announcements': 'Updated announcements',
            # Multiple line changes
            'lines-0-description': 'Updated service 1',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00',
            'lines-1-description': 'New service 2',
            'lines-1-qty': '1.00',
            'lines-1-unit_price': '75.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify ALL changes were applied together
        db.session.refresh(sample_invoice)
        
        # Invoice level changes
        assert sample_invoice.vat_rate_id == new_vat_rate.id
        assert sample_invoice.status == 'saadetud'
        assert sample_invoice.payment_terms == '30 päeva'
        assert sample_invoice.note == 'Complex edit test'
        assert sample_invoice.client_extra_info == 'Updated client info'
        assert sample_invoice.announcements == 'Updated announcements'
        
        # Line level changes
        assert len(sample_invoice.lines) == 2
        
        # Verify totals were recalculated correctly
        sample_invoice.calculate_totals()
        expected_subtotal = Decimal('300.00') + Decimal('75.00')  # 375.00
        expected_vat = expected_subtotal * Decimal('0.09')  # 33.75
        expected_total = expected_subtotal + expected_vat  # 408.75
        
        assert sample_invoice.subtotal == expected_subtotal
        assert sample_invoice.vat_amount == expected_vat
        assert sample_invoice.total == expected_total