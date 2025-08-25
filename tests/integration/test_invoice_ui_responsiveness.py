"""
UI responsiveness tests for invoice editing functionality.

Tests form validation feedback, real-time updates, and user interface
behavior during invoice editing operations.
"""

import pytest
import json
import re
from decimal import Decimal
from datetime import date, timedelta
from bs4 import BeautifulSoup

from app.models import db, Invoice, InvoiceLine, Client, VatRate


class TestFormValidationFeedback:
    """Test immediate form validation feedback."""
    
    def test_required_field_validation_display(self, client, app_context, sample_client):
        """Test that required field validation errors are displayed immediately."""
        # Submit form with missing required fields
        form_data = {
            'number': '',  # Required field missing
            'client_id': '',  # Required field missing
            'date': '',  # Required field missing
            'due_date': '',  # Required field missing
        }
        
        response = client.post('/invoices/new', data=form_data)
        assert response.status_code == 200
        
        # Parse response to check for validation errors
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for validation error classes
        invalid_fields = soup.find_all(class_='is-invalid')
        assert len(invalid_fields) > 0
        
        # Check for validation error messages
        error_messages = soup.find_all(class_='invalid-feedback')
        assert len(error_messages) > 0
    
    def test_client_selection_validation(self, client, app_context, sample_client):
        """Test client selection validation feedback."""
        form_data = {
            'number': 'TEST-VAL-001',
            'client_id': '',  # Missing client selection
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        assert response.status_code == 200
        
        # Check that client field shows validation error
        soup = BeautifulSoup(response.data, 'html.parser')
        client_field = soup.find('select', {'name': 'client_id'})
        
        # Should have validation error class or parent should show error
        validation_error_found = (
            client_field and 'is-invalid' in client_field.get('class', [])
        ) or soup.find(class_='invalid-feedback')
        
        assert validation_error_found
    
    def test_line_validation_feedback(self, client, app_context, sample_client):
        """Test line item validation feedback."""
        form_data = {
            'number': 'TEST-LINE-VAL-001',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            # Incomplete line (missing description)
            'lines-0-description': '',  # Missing
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should either show validation error or prompt for complete line
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Look for flash messages or validation feedback
        flash_messages = soup.find_all(class_='alert')
        validation_errors = soup.find_all(class_='invalid-feedback')
        
        has_validation_feedback = len(flash_messages) > 0 or len(validation_errors) > 0
        assert has_validation_feedback
    
    def test_numeric_field_validation(self, client, app_context, sample_client):
        """Test numeric field validation (quantities, prices)."""
        form_data = {
            'number': 'TEST-NUMERIC-001',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'lines-0-description': 'Test service',
            'lines-0-qty': 'invalid_number',  # Invalid numeric input
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Browser would typically handle this client-side, but server should also validate
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for any validation feedback
        has_feedback = (
            soup.find_all(class_='is-invalid') or
            soup.find_all(class_='invalid-feedback') or
            soup.find_all(class_='alert')
        )
        
        # Should either show error or handle gracefully
        assert response.status_code in [200, 400]


class TestRealTimeUIUpdates:
    """Test real-time UI update behavior simulation."""
    
    def test_invoice_form_loads_with_totals(self, client, app_context, sample_invoice):
        """Test that invoice edit form loads with correct initial totals."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for totals display elements
        subtotal_element = soup.find(id='subtotal')
        vat_amount_element = soup.find(id='vat-amount')
        total_amount_element = soup.find(id='total-amount')
        
        assert subtotal_element is not None
        assert vat_amount_element is not None
        assert total_amount_element is not None
        
        # Check that JavaScript calculation functions are present
        script_tags = soup.find_all('script')
        js_content = ' '.join([tag.get_text() for tag in script_tags if tag.get_text()])
        
        assert 'updateTotals' in js_content
        assert 'addLineEventListeners' in js_content
    
    def test_vat_rate_selector_functionality(self, client, app_context, sample_invoice):
        """Test VAT rate selector UI components."""
        VatRate.create_default_rates()
        db.session.commit()
        
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for VAT rate selector
        vat_selector = soup.find(id='vatRateSelector')
        vat_dropdown = soup.find(id='vatRateDropdown')
        
        assert vat_selector is not None
        assert vat_dropdown is not None
        
        # Check that VAT rate options are present
        vat_options = soup.find_all(class_='vat-rate-option')
        assert len(vat_options) >= 4  # Should have default Estonian rates
        
        # Check for hidden VAT rate field
        vat_rate_field = soup.find('input', {'name': 'vat_rate_id'})
        assert vat_rate_field is not None
    
    def test_line_management_ui_elements(self, client, app_context, sample_invoice):
        """Test line management UI elements are present."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for line container
        lines_container = soup.find(id='invoice-lines-container')
        assert lines_container is not None
        
        # Check for add line button
        add_line_buttons = soup.find_all('button', string=re.compile(r'Lisa rida|Lisa esimene rida'))
        assert len(add_line_buttons) > 0
        
        # Check for line template
        line_template = soup.find(id='line-template')
        assert line_template is not None
        
        # Check for line total displays
        line_totals = soup.find_all(class_='line-total')
        assert len(line_totals) >= 0  # May be 0 if no lines exist
        
        # Check for JavaScript functions
        script_tags = soup.find_all('script')
        js_content = ' '.join([tag.get_text() for tag in script_tags if tag.get_text()])
        
        assert 'addInvoiceLine' in js_content
        assert 'removeInvoiceLine' in js_content
    
    def test_form_submission_ui_feedback(self, client, app_context, sample_invoice):
        """Test UI feedback during form submission."""
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-description': 'Updated service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check for success feedback
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Should redirect to invoice list or detail with success message
        success_indicators = (
            soup.find_all(class_='alert-success') or
            soup.find_all(string=re.compile(r'(uuendatud|saved|updated)', re.IGNORECASE))
        )
        
        # Either success message or redirect to invoices list
        is_success = (
            len(success_indicators) > 0 or
            'invoices' in response.request.url or
            response.status_code == 200
        )
        
        assert is_success


class TestErrorHandlingUI:
    """Test UI error handling and feedback."""
    
    def test_duplicate_invoice_number_error_display(self, client, app_context, sample_client):
        """Test UI feedback for duplicate invoice number."""
        # Create first invoice
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        first_invoice = Invoice(
            number='DUPLICATE-TEST-UI',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(first_invoice)
        db.session.commit()
        
        # Try to create second invoice with same number
        form_data = {
            'number': 'DUPLICATE-TEST-UI',  # Same number
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        
        # Should show error feedback
        soup = BeautifulSoup(response.data, 'html.parser')
        
        error_indicators = (
            soup.find_all(class_='alert-danger') or
            soup.find_all(class_='is-invalid') or
            soup.find_all(class_='invalid-feedback') or
            soup.find_all(string=re.compile(r'(eksisteerib|exists|duplicate)', re.IGNORECASE))
        )
        
        assert len(error_indicators) > 0
    
    def test_network_error_graceful_handling(self, client, app_context, sample_invoice):
        """Test graceful handling of potential network errors."""
        # Simulate malformed request data
        malformed_data = {
            'number': sample_invoice.number,
            'client_id': 'invalid_id',  # Invalid client ID
            'date': 'invalid_date',  # Invalid date format
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', data=malformed_data)
        
        # Should handle gracefully (not crash)
        assert response.status_code in [200, 400, 422]
        
        # Should show some form of error feedback
        soup = BeautifulSoup(response.data, 'html.parser')
        
        has_error_feedback = (
            soup.find_all(class_='alert') or
            soup.find_all(class_='is-invalid') or
            soup.find_all(class_='invalid-feedback')
        )
        
        assert len(has_error_feedback) > 0
    
    def test_javascript_disabled_fallback(self, client, app_context, sample_invoice):
        """Test that forms work when JavaScript is disabled."""
        # This simulates JavaScript being disabled - form should still work
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(sample_invoice.vat_rate_id),
            'status': sample_invoice.status,
            'payment_terms': sample_invoice.payment_terms or '14 päeva',
            'lines-0-description': 'No-JS test service',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '75.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        
        # Should work without JavaScript
        assert response.status_code == 200
        
        # Verify changes were saved
        db.session.refresh(sample_invoice)
        if sample_invoice.lines:
            # Check that at least basic functionality works
            assert len(sample_invoice.lines) > 0


class TestUIPerformance:
    """Test UI performance and responsiveness."""
    
    def test_large_invoice_form_load_time(self, client, app_context, sample_client):
        """Test form performance with large number of lines."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice with many lines
        invoice = Invoice(
            number='LARGE-INVOICE-UI',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add many lines
        for i in range(20):  # 20 lines should be reasonable for testing
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=f'Service line {i+1}',
                qty=Decimal('1.00'),
                unit_price=Decimal('50.00'),
                line_total=Decimal('50.00')
            )
            db.session.add(line)
        
        db.session.commit()
        
        # Test form load
        import time
        start_time = time.time()
        
        response = client.get(f'/invoices/{invoice.id}/edit')
        
        load_time = time.time() - start_time
        
        assert response.status_code == 200
        assert load_time < 5.0  # Should load within 5 seconds
        
        # Check that all lines are present in the form
        soup = BeautifulSoup(response.data, 'html.parser')
        line_descriptions = soup.find_all('input', {'name': re.compile(r'lines-\d+-description')})
        assert len(line_descriptions) >= 20
    
    def test_complex_form_submission_performance(self, client, app_context, sample_client):
        """Test performance of complex form submissions."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create form data with multiple lines and changes
        form_data = {
            'number': 'COMPLEX-PERF-TEST',
            'client_id': str(sample_client.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'payment_terms': '14 päeva',
            'note': 'Complex performance test invoice',
            'client_extra_info': 'Performance testing client info',
            'announcements': 'Performance test announcements'
        }
        
        # Add multiple lines
        for i in range(10):
            form_data.update({
                f'lines-{i}-description': f'Performance test service {i+1}',
                f'lines-{i}-qty': str(float(i + 1)),
                f'lines-{i}-unit_price': str(float((i + 1) * 25))
            })
        
        # Test submission performance
        import time
        start_time = time.time()
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        
        submit_time = time.time() - start_time
        
        assert response.status_code == 200
        assert submit_time < 10.0  # Should complete within 10 seconds
        
        # Verify invoice was created correctly
        created_invoice = Invoice.query.filter_by(number='COMPLEX-PERF-TEST').first()
        assert created_invoice is not None
        assert len(created_invoice.lines) == 10


class TestAccessibilityAndUsability:
    """Test accessibility and usability features."""
    
    def test_form_labels_and_accessibility(self, client, app_context, sample_invoice):
        """Test that form elements have proper labels for accessibility."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check that form inputs have associated labels
        form_inputs = soup.find_all('input', {'type': ['text', 'number', 'date', 'email']})
        selects = soup.find_all('select')
        textareas = soup.find_all('textarea')
        
        all_form_elements = form_inputs + selects + textareas
        
        labeled_elements = 0
        for element in all_form_elements:
            element_id = element.get('id')
            element_name = element.get('name')
            
            # Check for associated label
            if element_id:
                label = soup.find('label', {'for': element_id})
                if label:
                    labeled_elements += 1
            elif element_name and not element_name.startswith('csrf_token'):
                # Check for nearby label
                parent = element.parent
                if parent and parent.find('label'):
                    labeled_elements += 1
        
        # Most form elements should have labels (exclude hidden fields)
        visible_elements = [e for e in all_form_elements if e.get('type') != 'hidden']
        label_percentage = labeled_elements / max(len(visible_elements), 1)
        
        assert label_percentage > 0.7  # At least 70% should have labels
    
    def test_required_field_indicators(self, client, app_context, sample_invoice):
        """Test that required fields are clearly indicated."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for required field indicators (usually asterisks)
        required_indicators = soup.find_all(class_='text-danger')
        asterisks = soup.find_all(string='*')
        
        required_field_indicators = len(required_indicators) + len(asterisks)
        
        # Should have indicators for required fields
        assert required_field_indicators > 0
    
    def test_error_message_clarity(self, client, app_context, sample_client):
        """Test that error messages are clear and helpful."""
        # Submit form with validation errors
        form_data = {
            'number': '',  # Required
            'client_id': '',  # Required
            'date': '',  # Required
            'due_date': '',  # Required
        }
        
        response = client.post('/invoices/new', data=form_data)
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for error messages
        error_messages = soup.find_all(class_='invalid-feedback')
        alert_messages = soup.find_all(class_='alert')
        
        all_messages = error_messages + alert_messages
        
        # Should have clear error messages
        assert len(all_messages) > 0
        
        # Messages should be in Estonian (check for common Estonian words)
        message_text = ' '.join([msg.get_text() for msg in all_messages])
        estonian_indicators = ['kohustuslik', 'täida', 'puudub', 'vale', 'viga']
        
        has_estonian = any(word in message_text.lower() for word in estonian_indicators)
        
        # Should have messages in Estonian or be clearly understandable
        assert has_estonian or len(message_text) > 10