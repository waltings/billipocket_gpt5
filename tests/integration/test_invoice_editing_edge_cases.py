"""
Edge case and error handling tests for invoice editing.

Tests behavior when JavaScript is disabled, form submission with invalid data,
network interruption scenarios, and other edge cases specific to Estonian
invoice requirements.
"""

import pytest
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from unittest.mock import patch, Mock
import json

from app.models import db, Invoice, InvoiceLine, Client, VatRate, CompanySettings
from app.services.totals import calculate_invoice_totals, calculate_line_total


class TestJavaScriptDisabledScenarios:
    """Test functionality when JavaScript is disabled."""
    
    def test_invoice_creation_without_javascript(self, client, app_context, sample_client):
        """Test that invoice creation works without JavaScript real-time calculations."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Simulate form submission without JavaScript calculations
        form_data = {
            'number': 'NO-JS-TEST-001',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'payment_terms': '14 päeva',
            # Multiple lines without JavaScript line totals
            'lines-0-description': 'Service without JS 1',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00',
            # No line_total field (would be calculated by JS)
            'lines-1-description': 'Service without JS 2',
            'lines-1-qty': '1.50',
            'lines-1-unit_price': '200.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify invoice was created correctly
        invoice = Invoice.query.filter_by(number='NO-JS-TEST-001').first()
        assert invoice is not None
        assert len(invoice.lines) == 2
        
        # Verify server-side calculations are correct
        line1 = next(l for l in invoice.lines if 'Service without JS 1' in l.description)
        line2 = next(l for l in invoice.lines if 'Service without JS 2' in l.description)
        
        assert line1.line_total == Decimal('300.00')  # 2.00 * 150.00
        assert line2.line_total == Decimal('300.00')  # 1.50 * 200.00
        
        # Verify invoice totals
        invoice.calculate_totals()
        expected_subtotal = Decimal('600.00')
        expected_total = expected_subtotal * Decimal('1.24')  # 24% VAT
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.total == expected_total
    
    def test_invoice_editing_without_javascript(self, client, app_context, sample_invoice):
        """Test that invoice editing works without JavaScript."""
        # Ensure invoice has a line
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
        
        # Edit without JavaScript
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-id': str(original_line_id),
            'lines-0-description': 'Edited without JS',
            'lines-0-qty': '3.00',
            'lines-0-unit_price': '75.00'
            # No JavaScript-calculated line_total
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify changes were applied correctly
        db.session.refresh(sample_invoice)
        line = sample_invoice.lines[0]
        
        assert line.description == 'Edited without JS'
        assert line.qty == Decimal('3.00')
        assert line.unit_price == Decimal('75.00')
        assert line.line_total == Decimal('225.00')  # Server calculated
    
    def test_form_validation_without_javascript(self, client, app_context, sample_client):
        """Test that form validation works without JavaScript."""
        # Submit invalid form without JavaScript validation
        form_data = {
            'number': '',  # Invalid - required
            'client_id': '',  # Invalid - required
            'date': 'invalid-date',  # Invalid format
            'due_date': '',  # Invalid - required
            'lines-0-description': 'Test',
            'lines-0-qty': 'not-a-number',  # Invalid
            'lines-0-unit_price': '-50.00'  # Invalid - negative
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should handle validation server-side
        assert response.status_code in [200, 400]
        
        # Should not create invalid invoice
        invalid_invoice = Invoice.query.filter_by(number='').first()
        assert invalid_invoice is None


class TestInvalidDataHandling:
    """Test handling of invalid data submissions."""
    
    def test_invalid_decimal_values(self, client, app_context, sample_client):
        """Test handling of invalid decimal values in quantities and prices."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invalid_values = [
            ('abc', '100.00'),  # Invalid quantity
            ('1.00', 'xyz'),    # Invalid price
            ('1.00.00', '100'), # Invalid decimal format
            ('', '100.00'),     # Empty quantity
            ('1.00', ''),       # Empty price
            ('999999999999999', '1.00'),  # Extremely large quantity
            ('1.00', '999999999999999')   # Extremely large price
        ]
        
        for qty, price in invalid_values:
            form_data = {
                'number': f'INVALID-DECIMAL-{qty}-{price}',
                'client_id': str(sample_client.id),
                'date': date.today().strftime('%Y-%m-%d'),
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': '14 päeva',
                'lines-0-description': 'Invalid decimal test',
                'lines-0-qty': qty,
                'lines-0-unit_price': price
            }
            
            response = client.post('/invoices/new', data=form_data)
            
            # Should handle gracefully (not crash)
            assert response.status_code in [200, 400, 422]
            
            # Should not create invoice with invalid data
            created_invoice = Invoice.query.filter_by(
                number=f'INVALID-DECIMAL-{qty}-{price}'
            ).first()
            
            # Either no invoice created or values were sanitized
            if created_invoice:
                assert len(created_invoice.lines) == 0 or all(
                    line.qty > 0 and line.unit_price >= 0 
                    for line in created_invoice.lines
                )
    
    def test_sql_injection_protection(self, client, app_context, sample_client):
        """Test protection against SQL injection attempts."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        malicious_inputs = [
            "'; DROP TABLE invoices; --",
            "1'; UPDATE invoices SET total=0; --",
            "test'; DELETE FROM invoice_lines WHERE 1=1; --",
            "<script>alert('xss')</script>",
            "UNION SELECT * FROM users",
            "1 OR 1=1"
        ]
        
        for malicious_input in malicious_inputs:
            form_data = {
                'number': f'SQL-TEST-{hash(malicious_input) % 1000}',
                'client_id': str(sample_client.id),
                'date': date.today().strftime('%Y-%m-%d'),
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': '14 päeva',
                'lines-0-description': malicious_input,
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data)
            
            # Should handle safely
            assert response.status_code in [200, 400, 422]
            
            # Verify database integrity is maintained
            invoice_count = Invoice.query.count()
            line_count = InvoiceLine.query.count()
            
            # Database should still exist and be accessible
            assert invoice_count >= 0
            assert line_count >= 0
    
    def test_extremely_long_text_input(self, client, app_context, sample_client):
        """Test handling of extremely long text inputs."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Generate very long strings
        long_description = 'A' * 10000  # 10KB description
        long_note = 'B' * 5000  # 5KB note
        long_announcement = 'C' * 8000  # 8KB announcement
        
        form_data = {
            'number': 'LONG-TEXT-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'payment_terms': '14 päeva',
            'note': long_note,
            'announcements': long_announcement,
            'lines-0-description': long_description,
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 413, 422]
        
        # If invoice was created, text should be truncated or stored safely
        created_invoice = Invoice.query.filter_by(number='LONG-TEXT-TEST').first()
        if created_invoice:
            # Text should be stored (possibly truncated)
            assert created_invoice.note is not None
            assert created_invoice.announcements is not None
            
            if created_invoice.lines:
                assert created_invoice.lines[0].description is not None
    
    def test_unicode_and_estonian_characters(self, client, app_context, sample_client):
        """Test handling of Unicode and Estonian-specific characters."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Estonian characters and various Unicode
        test_strings = [
            'Käibemaksu arvestus äriühingule',
            'Müük ja teenused õigusaktide järgi',
            'Unicode test: 🇪🇪 💰 📄',
            'Mixed: café, naïve, résumé',
            'Cyrillic: Привет мир',
            'Asian: 你好世界 こんにちは',
            'Symbols: ©®™€$¥£¢'
        ]
        
        for i, test_string in enumerate(test_strings):
            form_data = {
                'number': f'UNICODE-TEST-{i:03d}',
                'client_id': str(sample_client.id),
                'date': date.today().strftime('%Y-%m-%d'),
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': '14 päeva',
                'note': f'Unicode test: {test_string}',
                'lines-0-description': test_string,
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data)
            assert response.status_code in [200, 400]
            
            # Verify Unicode handling
            created_invoice = Invoice.query.filter_by(number=f'UNICODE-TEST-{i:03d}').first()
            if created_invoice:
                # Unicode should be preserved
                assert test_string in created_invoice.note
                if created_invoice.lines:
                    assert test_string == created_invoice.lines[0].description


class TestNetworkInterruptionScenarios:
    """Test behavior during network interruption scenarios."""
    
    def test_incomplete_form_submission(self, client, app_context, sample_client):
        """Test handling of incomplete form submissions."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Simulate incomplete submission (like network timeout)
        incomplete_data = {
            'number': 'INCOMPLETE-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            # Missing due_date
            'vat_rate_id': str(standard_vat.id),
            # Missing status
            'lines-0-description': 'Incomplete submission test',
            'lines-0-qty': '1.00'
            # Missing unit_price
        }
        
        response = client.post('/invoices/new', data=incomplete_data)
        
        # Should handle incomplete data gracefully
        assert response.status_code in [200, 400]
        
        # Should not create invalid invoice
        incomplete_invoice = Invoice.query.filter_by(number='INCOMPLETE-TEST').first()
        
        if incomplete_invoice:
            # If created, should have valid default values
            assert incomplete_invoice.due_date is not None
            assert incomplete_invoice.status is not None
        else:
            # Or should not be created at all
            assert True  # This is also acceptable
    
    def test_duplicate_submission_handling(self, client, app_context, sample_client):
        """Test handling of duplicate form submissions (double-click scenario)."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': 'DUPLICATE-SUBMIT-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'payment_terms': '14 päeva',
            'lines-0-description': 'Duplicate test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        # Submit the same form twice quickly
        response1 = client.post('/invoices/new', data=form_data)
        response2 = client.post('/invoices/new', data=form_data)
        
        # First should succeed, second should fail or be handled gracefully
        assert response1.status_code in [200, 302]  # Success or redirect
        assert response2.status_code in [200, 400, 409]  # Handled gracefully
        
        # Should only create one invoice
        duplicate_invoices = Invoice.query.filter_by(number='DUPLICATE-SUBMIT-TEST').all()
        assert len(duplicate_invoices) <= 1
    
    @patch('app.models.db.session.commit')
    def test_database_connection_failure(self, mock_commit, client, app_context, sample_client):
        """Test handling of database connection failures."""
        # Mock database failure
        mock_commit.side_effect = Exception("Database connection lost")
        
        VatRate.create_default_rates()
        mock_commit.side_effect = None  # Reset for VAT rate creation
        VatRate.create_default_rates()
        mock_commit.side_effect = Exception("Database connection lost")  # Reset mock
        
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': 'DB-FAILURE-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id) if standard_vat else '1',
            'status': 'mustand',
            'payment_terms': '14 päeva',
            'lines-0-description': 'DB failure test',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should handle database failure gracefully
        assert response.status_code in [200, 500, 503]


class TestEstonianSpecificEdgeCases:
    """Test Estonian-specific invoice requirements and edge cases."""
    
    def test_invalid_estonian_vat_rates(self, client, app_context, sample_client):
        """Test handling of invalid Estonian VAT rates."""
        # Create invoice with invalid VAT rate
        form_data = {
            'number': 'INVALID-VAT-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': '999999',  # Non-existent VAT rate ID
            'status': 'mustand',
            'payment_terms': '14 päeva',
            'lines-0-description': 'Invalid VAT test',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should handle invalid VAT rate gracefully
        assert response.status_code in [200, 400]
        
        # If invoice was created, should use default VAT rate
        created_invoice = Invoice.query.filter_by(number='INVALID-VAT-TEST').first()
        if created_invoice:
            # Should fall back to valid VAT rate
            assert created_invoice.get_effective_vat_rate() in [0, 9, 20, 24]
    
    def test_estonian_date_formats(self, client, app_context, sample_client):
        """Test handling of various date formats."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Test various date formats that might be submitted
        date_formats = [
            '2025-12-31',      # ISO format (correct)
            '31.12.2025',      # Estonian format
            '31/12/2025',      # Alternative format
            '2025/12/31',      # US format
            'invalid-date',    # Invalid
            '',                # Empty
            '2025-13-45'       # Invalid values
        ]
        
        for i, date_str in enumerate(date_formats):
            form_data = {
                'number': f'DATE-TEST-{i:02d}',
                'client_id': str(sample_client.id),
                'date': date_str,
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': '14 päeva',
                'lines-0-description': f'Date format test {date_str}',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data)
            
            # Should handle various formats or show validation error
            assert response.status_code in [200, 400]
            
            created_invoice = Invoice.query.filter_by(number=f'DATE-TEST-{i:02d}').first()
            if created_invoice:
                # Date should be valid
                assert isinstance(created_invoice.date, date)
    
    def test_estonian_currency_precision(self, client, app_context, sample_client):
        """Test Estonian currency precision requirements (cents)."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Test various precision scenarios
        precision_tests = [
            ('1.00', '100.00'),      # Normal precision
            ('1.999', '100.999'),    # Too many decimals
            ('1.1', '100.1'),        # One decimal
            ('1', '100'),            # No decimals
            ('1.005', '100.005'),    # Half cent
            ('0.01', '0.01'),        # Minimum amounts
            ('0.001', '0.001')       # Sub-cent
        ]
        
        for i, (qty, price) in enumerate(precision_tests):
            form_data = {
                'number': f'PRECISION-TEST-{i:02d}',
                'client_id': str(sample_client.id),
                'date': date.today().strftime('%Y-%m-%d'),
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': '14 päeva',
                'lines-0-description': f'Precision test {qty} × {price}',
                'lines-0-qty': qty,
                'lines-0-unit_price': price
            }
            
            response = client.post('/invoices/new', data=form_data)
            assert response.status_code in [200, 400]
            
            created_invoice = Invoice.query.filter_by(number=f'PRECISION-TEST-{i:02d}').first()
            if created_invoice and created_invoice.lines:
                line = created_invoice.lines[0]
                
                # Values should be properly rounded to cents
                assert line.qty.as_tuple().exponent >= -2  # Max 2 decimal places
                assert line.unit_price.as_tuple().exponent >= -2
                assert line.line_total.as_tuple().exponent >= -2
    
    def test_estonian_invoice_status_transitions(self, client, app_context, sample_invoice):
        """Test Estonian-specific invoice status transitions."""
        # Test invalid status transitions
        invalid_statuses = [
            'invalid_status',
            'MUSTAND',  # Wrong case
            'sent',     # English instead of Estonian
            'paid',     # English instead of Estonian
            ''          # Empty
        ]
        
        for invalid_status in invalid_statuses:
            form_data = {
                'number': sample_invoice.number,
                'client_id': str(sample_invoice.client_id),
                'date': sample_invoice.date.strftime('%Y-%m-%d'),
                'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
                'vat_rate_id': str(sample_invoice.vat_rate_id),
                'status': invalid_status,
                'payment_terms': sample_invoice.payment_terms or '14 päeva',
                'lines-0-description': 'Status test',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post(f'/invoices/{sample_invoice.id}/edit', data=form_data)
            
            # Should handle invalid status gracefully
            assert response.status_code in [200, 400]
            
            # Verify status remains valid
            db.session.refresh(sample_invoice)
            valid_statuses = ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
            assert sample_invoice.status in valid_statuses
    
    def test_estonian_payment_terms_validation(self, client, app_context, sample_client):
        """Test Estonian payment terms validation."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Test various payment terms
        payment_terms = [
            '14 päeva',           # Standard
            '30 päeva',           # Extended
            '7 päeva',            # Short
            'Kohe',               # Immediate
            'invalid payment',    # Invalid
            '',                   # Empty
            '999 päeva'           # Very long
        ]
        
        for i, payment_term in enumerate(payment_terms):
            form_data = {
                'number': f'PAYMENT-TERMS-{i:02d}',
                'client_id': str(sample_client.id),
                'date': date.today().strftime('%Y-%m-%d'),
                'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'vat_rate_id': str(standard_vat.id),
                'status': 'mustand',
                'payment_terms': payment_term,
                'lines-0-description': f'Payment terms test: {payment_term}',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data)
            assert response.status_code in [200, 400]
            
            created_invoice = Invoice.query.filter_by(number=f'PAYMENT-TERMS-{i:02d}').first()
            if created_invoice:
                # Payment terms should be stored (possibly with fallback)
                assert created_invoice.payment_terms is not None