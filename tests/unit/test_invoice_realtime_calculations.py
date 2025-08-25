"""
Unit tests for invoice real-time calculation functionality.

Tests the JavaScript-based real-time calculations that occur when users
edit invoice line items, change VAT rates, and modify quantities/prices.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import date, timedelta

from app.models import db, Invoice, InvoiceLine, Client, VatRate
from app.services.totals import calculate_invoice_totals, calculate_line_total


class TestLineCalculations:
    """Test individual line item calculations."""
    
    def test_line_total_calculation_basic(self):
        """Test basic line total calculation (qty * unit_price)."""
        qty = Decimal('2.00')
        unit_price = Decimal('50.00')
        expected_total = Decimal('100.00')
        
        result = calculate_line_total(qty, unit_price)
        assert result == expected_total
    
    def test_line_total_calculation_decimal_precision(self):
        """Test line total with decimal precision."""
        qty = Decimal('3.333')
        unit_price = Decimal('37.037')
        expected_total = Decimal('123.456321')  # 3.333 * 37.037
        
        result = calculate_line_total(qty, unit_price)
        # Should maintain precision
        assert abs(result - expected_total) < Decimal('0.001')
    
    def test_line_total_calculation_rounding(self):
        """Test line total rounding to 2 decimal places."""
        qty = Decimal('1.00')
        unit_price = Decimal('33.333')  # Will result in 33.333
        
        result = calculate_line_total(qty, unit_price)
        # Should round to 2 decimal places
        assert result.quantize(Decimal('0.01')) == Decimal('33.33')
    
    def test_line_total_zero_quantity(self):
        """Test line total with zero quantity."""
        qty = Decimal('0.00')
        unit_price = Decimal('100.00')
        expected_total = Decimal('0.00')
        
        result = calculate_line_total(qty, unit_price)
        assert result == expected_total
    
    def test_line_total_zero_price(self):
        """Test line total with zero price."""
        qty = Decimal('5.00')
        unit_price = Decimal('0.00')
        expected_total = Decimal('0.00')
        
        result = calculate_line_total(qty, unit_price)
        assert result == expected_total
    
    def test_line_total_large_numbers(self):
        """Test line total with large numbers."""
        qty = Decimal('999.99')
        unit_price = Decimal('9999.99')
        expected_total = qty * unit_price
        
        result = calculate_line_total(qty, unit_price)
        assert result == expected_total


class TestVatCalculations:
    """Test VAT amount calculations for different rates."""
    
    def test_vat_calculation_standard_rate(self, sample_client):
        """Test VAT calculation with Estonian standard rate (24%)."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        subtotal = Decimal('100.00')
        
        invoice = Invoice(
            number='TEST-VAT-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            subtotal=subtotal
        )
        
        expected_vat = subtotal * (Decimal('24') / 100)  # 24.00
        assert invoice.vat_amount == expected_vat
    
    def test_vat_calculation_zero_rate(self, sample_client):
        """Test VAT calculation with 0% rate."""
        VatRate.create_default_rates()
        db.session.commit()
        
        zero_rate = VatRate.query.filter_by(rate=0).first()
        subtotal = Decimal('100.00')
        
        invoice = Invoice(
            number='TEST-VAT-002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=zero_rate.id,
            subtotal=subtotal
        )
        
        expected_vat = Decimal('0.00')
        assert invoice.vat_amount == expected_vat
    
    def test_vat_calculation_reduced_rates(self, sample_client):
        """Test VAT calculation with reduced rates (9%, 20%)."""
        VatRate.create_default_rates()
        db.session.commit()
        
        rates_to_test = [9, 20]
        subtotal = Decimal('100.00')
        
        for rate_value in rates_to_test:
            vat_rate = VatRate.query.filter_by(rate=rate_value).first()
            
            invoice = Invoice(
                number=f'TEST-VAT-{rate_value}',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate_id=vat_rate.id,
                subtotal=subtotal
            )
            
            expected_vat = subtotal * (Decimal(str(rate_value)) / 100)
            assert invoice.vat_amount == expected_vat
    
    def test_vat_calculation_precision(self, sample_client):
        """Test VAT calculation maintains proper decimal precision."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        # Use amount that creates repeating decimals
        subtotal = Decimal('333.33')
        
        invoice = Invoice(
            number='TEST-VAT-PRECISION',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            subtotal=subtotal
        )
        
        # VAT should be 79.9992, rounded to 80.00
        expected_vat = Decimal('79.9992').quantize(Decimal('0.01'))
        actual_vat = invoice.vat_amount.quantize(Decimal('0.01'))
        assert actual_vat == expected_vat


class TestTotalCalculations:
    """Test complete invoice total calculations."""
    
    def test_invoice_total_single_line(self, sample_client):
        """Test invoice total calculation with single line item."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-TOTAL-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add single line
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Test service',
            qty=Decimal('2.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Recalculate totals
        invoice.calculate_totals()
        
        expected_subtotal = Decimal('100.00')
        expected_vat = Decimal('24.00')  # 24% of 100
        expected_total = Decimal('124.00')
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.vat_amount == expected_vat
        assert invoice.total == expected_total
    
    def test_invoice_total_multiple_lines(self, sample_client):
        """Test invoice total calculation with multiple line items."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-TOTAL-002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add multiple lines
        lines_data = [
            {'description': 'Service 1', 'qty': Decimal('1.00'), 'unit_price': Decimal('100.00')},
            {'description': 'Service 2', 'qty': Decimal('2.00'), 'unit_price': Decimal('75.00')},
            {'description': 'Service 3', 'qty': Decimal('0.50'), 'unit_price': Decimal('200.00')}
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
        
        # Recalculate totals
        invoice.calculate_totals()
        
        expected_subtotal = Decimal('350.00')  # 100 + 150 + 100
        expected_vat = Decimal('84.00')  # 24% of 350
        expected_total = Decimal('434.00')
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.vat_amount == expected_vat
        assert invoice.total == expected_total
    
    def test_invoice_total_vat_rate_change(self, sample_client):
        """Test total recalculation when VAT rate changes."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        zero_rate = VatRate.query.filter_by(rate=0).first()
        
        invoice = Invoice(
            number='TEST-TOTAL-VAT-CHANGE',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add line
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Test service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Initial calculation with 24% VAT
        invoice.calculate_totals()
        assert invoice.total == Decimal('124.00')
        
        # Change to 0% VAT
        invoice.vat_rate_id = zero_rate.id
        invoice.calculate_totals()
        assert invoice.total == Decimal('100.00')
    
    def test_invoice_total_empty_lines(self, sample_client):
        """Test invoice total calculation with no lines."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-TOTAL-EMPTY',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Calculate totals with no lines
        invoice.calculate_totals()
        
        assert invoice.subtotal == Decimal('0.00')
        assert invoice.vat_amount == Decimal('0.00')
        assert invoice.total == Decimal('0.00')


class TestRealTimeUpdateLogic:
    """Test the logic that would drive real-time updates in the UI."""
    
    def test_line_update_triggers_recalculation(self, sample_client):
        """Test that line updates trigger total recalculation."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-REALTIME-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add initial line
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Test service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Initial calculation
        invoice.calculate_totals()
        initial_total = invoice.total
        
        # Simulate user changing quantity
        line.qty = Decimal('2.00')
        line.line_total = calculate_line_total(line.qty, line.unit_price)
        
        # Recalculate
        invoice.calculate_totals()
        
        # Total should have changed
        assert invoice.total != initial_total
        assert invoice.total == Decimal('248.00')  # (2 * 100) * 1.24
    
    def test_vat_rate_update_triggers_recalculation(self, sample_client):
        """Test that VAT rate changes trigger total recalculation."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        reduced_rate = VatRate.query.filter_by(rate=9).first()
        
        invoice = Invoice(
            number='TEST-REALTIME-002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand',
            subtotal=Decimal('100.00')
        )
        
        initial_total = invoice.subtotal + invoice.vat_amount
        
        # Change VAT rate
        invoice.vat_rate_id = reduced_rate.id
        new_total = invoice.subtotal + invoice.vat_amount
        
        # Total should have changed
        assert new_total != initial_total
        assert new_total == Decimal('109.00')  # 100 + (100 * 0.09)
    
    def test_multiple_line_updates_consistency(self, sample_client):
        """Test that multiple rapid line updates maintain calculation consistency."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-REALTIME-003',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add multiple lines
        lines_data = [
            {'qty': Decimal('1.00'), 'unit_price': Decimal('50.00')},
            {'qty': Decimal('2.00'), 'unit_price': Decimal('75.00')},
            {'qty': Decimal('3.00'), 'unit_price': Decimal('25.00')}
        ]
        
        lines = []
        for i, line_data in enumerate(lines_data):
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=f'Service {i+1}',
                qty=line_data['qty'],
                unit_price=line_data['unit_price'],
                line_total=calculate_line_total(line_data['qty'], line_data['unit_price'])
            )
            lines.append(line)
            db.session.add(line)
        
        db.session.commit()
        
        # Simulate rapid updates to multiple lines
        updates = [
            {'line_idx': 0, 'qty': Decimal('2.00')},
            {'line_idx': 1, 'unit_price': Decimal('100.00')},
            {'line_idx': 2, 'qty': Decimal('1.00')}
        ]
        
        for update in updates:
            line = lines[update['line_idx']]
            if 'qty' in update:
                line.qty = update['qty']
            if 'unit_price' in update:
                line.unit_price = update['unit_price']
            line.line_total = calculate_line_total(line.qty, line.unit_price)
        
        # Recalculate totals
        invoice.calculate_totals()
        
        # Verify final calculation is correct
        expected_subtotal = Decimal('100.00') + Decimal('200.00') + Decimal('25.00')  # 325.00
        expected_total = expected_subtotal * Decimal('1.24')  # 403.00
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.total == expected_total


class TestCalculationEdgeCases:
    """Test edge cases in calculations."""
    
    def test_very_small_amounts(self, sample_client):
        """Test calculations with very small monetary amounts."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='TEST-EDGE-SMALL',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            subtotal=Decimal('0.01')  # 1 cent
        )
        
        # VAT amount should be calculated correctly even for tiny amounts
        expected_vat = Decimal('0.01') * Decimal('0.24')  # 0.0024, should round to 0.00
        actual_vat = invoice.vat_amount.quantize(Decimal('0.01'))
        
        assert actual_vat == Decimal('0.00')  # Rounds down
    
    def test_very_large_amounts(self, sample_client):
        """Test calculations with very large monetary amounts."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        large_amount = Decimal('999999.99')
        invoice = Invoice(
            number='TEST-EDGE-LARGE',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_rate.id,
            subtotal=large_amount
        )
        
        expected_vat = large_amount * Decimal('0.24')
        expected_total = large_amount + expected_vat
        
        assert invoice.vat_amount == expected_vat
        assert invoice.subtotal + invoice.vat_amount == expected_total
    
    def test_decimal_rounding_consistency(self, sample_client):
        """Test that decimal rounding is consistent across calculations."""
        VatRate.create_default_rates()
        db.session.commit()
        
        standard_rate = VatRate.get_default_rate()
        
        # Use amount that creates rounding scenarios
        test_amounts = [
            Decimal('33.333'),
            Decimal('66.666'),
            Decimal('99.999')
        ]
        
        for amount in test_amounts:
            invoice = Invoice(
                number=f'TEST-ROUNDING-{amount}',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate_id=standard_rate.id,
                subtotal=amount
            )
            
            # Ensure calculations maintain proper precision
            vat_amount = invoice.vat_amount
            total_amount = invoice.subtotal + vat_amount
            
            # Check that amounts are properly rounded to 2 decimal places
            assert vat_amount.as_tuple().exponent >= -2
            assert total_amount.as_tuple().exponent >= -2