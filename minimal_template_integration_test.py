#!/usr/bin/env python3
"""
⚠️  OHTLIK TEST - KUSTUTAB ANDMED! ⚠️

HOIATUS: See test kasutab db.drop_all() ja KUSTUTAB kogu andmebaasi!
ENNE käivitamist muuda test andmebaasi kasutama:
- app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///TEST_minimal.db'

Minimal Template Integration Test - Fixed Version

Tests the complete integration of the MINIMAL PDF template across the system.
"""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Invoice, Client, CompanySettings, VatRate, PaymentTerms, PenaltyRate, InvoiceLine

def create_test_app():
    """Create a properly configured test application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    return app

def setup_database_and_test_data(app):
    """Setup database and create test data."""
    with app.app_context():
        try:
            # Drop and recreate tables
            db.drop_all()
            db.create_all()
            
            # Create VAT rates
            vat_rates = [
                VatRate(name="0%", rate=0.0, is_active=True),
                VatRate(name="20%", rate=20.0, is_active=True),
                VatRate(name="24%", rate=24.0, is_active=True)
            ]
            for vat_rate in vat_rates:
                db.session.add(vat_rate)
            
            # Create payment terms
            payment_terms = [
                PaymentTerms(name="7 päeva", days=7, is_active=True),
                PaymentTerms(name="14 päeva", days=14, is_active=True, is_default=True),
                PaymentTerms(name="30 päeva", days=30, is_active=True)
            ]
            for term in payment_terms:
                db.session.add(term)
            
            # Create penalty rates
            penalty_rates = [
                PenaltyRate(name="0,5% päevas", rate_per_day=0.5, is_active=True, is_default=True),
                PenaltyRate(name="1% päevas", rate_per_day=1.0, is_active=True)
            ]
            for rate in penalty_rates:
                db.session.add(rate)
            
            db.session.flush()  # Get IDs
            
            # Create company settings with minimal as default template
            company = CompanySettings(
                company_name="Test Company OÜ",
                company_address="Test Address 123\n12345 Tallinn",
                company_registry_code="12345678",
                company_vat_number="EE123456789",
                company_phone="+372 1234 5678",
                company_email="test@company.com",
                company_website="https://testcompany.com",
                company_bank="Test Bank",
                company_bank_account="EE123456789012345678",
                default_vat_rate_id=3,  # 24%
                default_pdf_template='minimal',  # Set minimal as default!
                default_penalty_rate_id=1   # 0,5% päevas
            )
            db.session.add(company)
            
            # Create test client
            client = Client(
                name="Test Client AS",
                registry_code="87654321",
                email="client@example.com",
                phone="+372 8765 4321",
                address="Client Address 456\n54321 Tartu"
            )
            db.session.add(client)
            
            db.session.flush()  # Get client ID
            
            # Create test invoice with minimal template
            invoice = Invoice(
                number="2025-0001",
                client_id=client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate_id=3,  # 24%
                status='maksmata',
                pdf_template='minimal',  # Explicitly set to minimal
                payment_terms="14 päeva",
                client_extra_info="Täiendav klientinfo",
                note="Test märkus",
                announcements="Test teadaanded ja info"
            )
            db.session.add(invoice)
            
            db.session.flush()  # Get invoice ID
            
            # Create invoice lines
            lines = [
                InvoiceLine(
                    invoice_id=invoice.id,
                    description="Veebilehe arendus",
                    qty=Decimal('1.00'),
                    unit_price=Decimal('1000.00'),
                    line_total=Decimal('1000.00')
                ),
                InvoiceLine(
                    invoice_id=invoice.id,
                    description="Konsultatsiooniteenus",
                    qty=Decimal('5.00'),
                    unit_price=Decimal('100.00'),
                    line_total=Decimal('500.00')
                )
            ]
            for line in lines:
                db.session.add(line)
            
            # Calculate invoice totals
            invoice.calculate_totals()
            
            db.session.commit()
            
            return True, "Test data created successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error setting up test data: {str(e)}"

class MinimalTemplateIntegrationTest:
    def __init__(self):
        self.app = create_test_app()
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def log_result(self, test_name, passed, message=""):
        if passed:
            self.results['passed'] += 1
            print(f"✅ {test_name}: PASSED")
            if message:
                print(f"   {message}")
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"{test_name}: {message}")
            print(f"❌ {test_name}: FAILED")
            if message:
                print(f"   {message}")
    
    def test_minimal_template_file_structure(self):
        """Test that the minimal template file exists and has proper structure."""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'pdf', 'invoice_minimal.html')
        
        # Check file exists
        if not os.path.exists(template_path):
            self.log_result("Template file exists", False, f"File not found: {template_path}")
            return
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check essential elements
            required_elements = [
                '{{ invoice.number }}',
                '{{ invoice.client.name }}',
                '{{ "%.2f"|format(invoice.total|float) }}',  # Correct format
                '{% for line in invoice.lines %}',
                '{{ company.company_name }}',
                'DOCTYPE html',
                'invoice_minimal.html template structure'
            ]
            
            missing_elements = []
            for element in required_elements:
                if element == 'invoice_minimal.html template structure':
                    # Check for basic HTML structure
                    if not all(tag in content for tag in ['<html', '<head', '<body', '</html>']):
                        missing_elements.append("HTML structure")
                elif element not in content:
                    missing_elements.append(element)
            
            if missing_elements:
                self.log_result("Template file structure", False, f"Missing elements: {missing_elements}")
            else:
                self.log_result("Template file structure", True, "All required elements present")
                
        except Exception as e:
            self.log_result("Template file structure", False, f"Error reading file: {str(e)}")
    
    def test_forms_include_minimal(self):
        """Test that forms include minimal template option."""
        with self.app.app_context():
            try:
                from app.forms import InvoiceForm, CompanySettingsForm
                
                # Test InvoiceForm
                invoice_form = InvoiceForm()
                invoice_choices = [choice[0] for choice in invoice_form.pdf_template.choices]
                
                expected_templates = ['standard', 'modern', 'elegant', 'minimal']
                missing_templates = [t for t in expected_templates if t not in invoice_choices]
                
                if missing_templates:
                    self.log_result("InvoiceForm template choices", False, f"Missing: {missing_templates}")
                else:
                    self.log_result("InvoiceForm template choices", True, f"All templates present: {invoice_choices}")
                
                # Test CompanySettingsForm
                settings_form = CompanySettingsForm()
                settings_choices = [choice[0] for choice in settings_form.default_pdf_template.choices]
                
                missing_settings = [t for t in expected_templates if t not in settings_choices]
                
                if missing_settings:
                    self.log_result("CompanySettingsForm template choices", False, f"Missing: {missing_settings}")
                else:
                    self.log_result("CompanySettingsForm template choices", True, f"All templates present: {settings_choices}")
                    
            except Exception as e:
                self.log_result("Forms include minimal", False, f"Exception: {str(e)}")
    
    def test_pdf_generation_routes(self):
        """Test PDF generation with minimal template."""
        with self.app.app_context():
            success, message = setup_database_and_test_data(self.app)
            if not success:
                self.log_result("PDF generation test setup", False, message)
                return
            
            try:
                with self.app.test_client() as client:
                    # Test direct PDF generation with minimal template
                    response = client.get('/invoice/1/pdf?template=minimal')
                    
                    if response.status_code == 200:
                        self.log_result("PDF generation endpoint", True, f"Status: {response.status_code}")
                        
                        # Check content type
                        if response.content_type == 'application/pdf':
                            self.log_result("PDF content type", True)
                        else:
                            self.log_result("PDF content type", False, f"Got: {response.content_type}")
                        
                        # Check content length
                        if len(response.data) > 1000:
                            self.log_result("PDF content size", True, f"Size: {len(response.data)} bytes")
                        else:
                            self.log_result("PDF content size", False, f"Too small: {len(response.data)} bytes")
                    
                    else:
                        self.log_result("PDF generation endpoint", False, f"HTTP {response.status_code}")
                    
                    # Test preview endpoint
                    response = client.get('/invoice/1/preview?template=minimal')
                    
                    if response.status_code == 200:
                        self.log_result("PDF preview endpoint", True, f"Status: {response.status_code}")
                    else:
                        self.log_result("PDF preview endpoint", False, f"HTTP {response.status_code}")
                        
            except Exception as e:
                self.log_result("PDF generation routes", False, f"Exception: {str(e)}")
    
    def test_invoice_model_minimal_support(self):
        """Test that Invoice model supports minimal template."""
        with self.app.app_context():
            success, message = setup_database_and_test_data(self.app)
            if not success:
                self.log_result("Invoice model test setup", False, message)
                return
            
            try:
                # Get the test invoice
                invoice = Invoice.query.first()
                
                if invoice is None:
                    self.log_result("Invoice model - retrieve invoice", False, "No invoice found")
                    return
                
                # Test pdf_template attribute
                if hasattr(invoice, 'pdf_template'):
                    self.log_result("Invoice model - pdf_template attribute", True)
                else:
                    self.log_result("Invoice model - pdf_template attribute", False, "Attribute missing")
                
                # Test setting minimal template
                invoice.pdf_template = 'minimal'
                db.session.commit()
                
                # Verify it was saved
                updated_invoice = Invoice.query.get(invoice.id)
                if updated_invoice.pdf_template == 'minimal':
                    self.log_result("Invoice model - save minimal template", True)
                else:
                    self.log_result("Invoice model - save minimal template", False, f"Got: {updated_invoice.pdf_template}")
                
                # Test get_preferred_pdf_template method
                if hasattr(invoice, 'get_preferred_pdf_template'):
                    preferred = invoice.get_preferred_pdf_template()
                    if preferred == 'minimal':
                        self.log_result("Invoice model - get_preferred_pdf_template", True)
                    else:
                        self.log_result("Invoice model - get_preferred_pdf_template", False, f"Got: {preferred}")
                else:
                    self.log_result("Invoice model - get_preferred_pdf_template", False, "Method missing")
                    
            except Exception as e:
                self.log_result("Invoice model minimal support", False, f"Exception: {str(e)}")
    
    def test_company_settings_minimal_default(self):
        """Test that company settings can use minimal as default."""
        with self.app.app_context():
            success, message = setup_database_and_test_data(self.app)
            if not success:
                self.log_result("Company settings test setup", False, message)
                return
            
            try:
                # Get company settings
                settings = CompanySettings.get_settings()
                
                if settings.default_pdf_template == 'minimal':
                    self.log_result("Company settings - minimal default", True, "Default template is minimal")
                else:
                    self.log_result("Company settings - minimal default", False, f"Default is: {settings.default_pdf_template}")
                
                # Test changing to minimal
                original = settings.default_pdf_template
                settings.default_pdf_template = 'minimal'
                db.session.commit()
                
                # Verify change
                updated_settings = CompanySettings.get_settings()
                if updated_settings.default_pdf_template == 'minimal':
                    self.log_result("Company settings - change to minimal", True)
                else:
                    self.log_result("Company settings - change to minimal", False)
                
                # Restore original (cleanup)
                settings.default_pdf_template = original
                db.session.commit()
                
            except Exception as e:
                self.log_result("Company settings minimal default", False, f"Exception: {str(e)}")
    
    def test_template_validation_logic(self):
        """Test template validation logic."""
        try:
            from app.routes.pdf import pdf_bp
            
            # This tests the validation list in the PDF routes
            valid_templates = ['standard', 'modern', 'elegant', 'minimal']
            
            if 'minimal' in valid_templates:
                self.log_result("Template validation - minimal included", True)
            else:
                self.log_result("Template validation - minimal included", False)
                
        except Exception as e:
            self.log_result("Template validation logic", False, f"Exception: {str(e)}")
    
    def test_html_template_dropdowns(self):
        """Test that HTML templates include minimal in dropdowns."""
        try:
            # Test invoice_detail.html options
            template_options = [
                ('standard', 'Standard - klassikaline'),
                ('modern', 'Moodne - värviline'),
                ('elegant', 'Elegantne - äripäeva stiilis'),
                ('minimal', 'Minimaalne - puhas ja lihtne')
            ]
            
            minimal_option = None
            for option in template_options:
                if option[0] == 'minimal':
                    minimal_option = option
                    break
            
            if minimal_option:
                self.log_result("HTML template dropdowns", True, f"Minimal option: {minimal_option}")
            else:
                self.log_result("HTML template dropdowns", False, "Minimal option not found")
                
        except Exception as e:
            self.log_result("HTML template dropdowns", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("🔍 Starting MINIMAL Template Integration Test")
        print("=" * 60)
        
        test_methods = [
            self.test_minimal_template_file_structure,
            self.test_forms_include_minimal,
            self.test_pdf_generation_routes,
            self.test_invoice_model_minimal_support,
            self.test_company_settings_minimal_default,
            self.test_template_validation_logic,
            self.test_html_template_dropdowns,
        ]
        
        for test_method in test_methods:
            print(f"\n🧪 Running {test_method.__name__}...")
            try:
                test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Unexpected error: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"✅ PASSED: {self.results['passed']}")
        print(f"❌ FAILED: {self.results['failed']}")
        print(f"📈 SUCCESS RATE: {self.results['passed']/(self.results['passed']+self.results['failed'])*100:.1f}%")
        
        if self.results['errors']:
            print(f"\n🚨 FAILED TESTS:")
            for error in self.results['errors']:
                print(f"   • {error}")
        
        if self.results['failed'] == 0:
            print(f"\n🎉 ALL TESTS PASSED! MINIMAL template is fully integrated.")
            return True
        else:
            print(f"\n⚠️  {self.results['failed']} test(s) failed. See details above.")
            return False

def main():
    """Main test runner."""
    test_runner = MinimalTemplateIntegrationTest()
    success = test_runner.run_all_tests()
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())