from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from decimal import Decimal

db = SQLAlchemy()


class VatRate(db.Model):
    """VAT rate model for storing different VAT percentages."""
    __tablename__ = 'vat_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # e.g., "Standardmäär (24%)"
    rate = db.Column(db.Numeric(5, 2), nullable=False, unique=True)  # e.g., 24.00
    description = db.Column(db.String(255), nullable=True)  # Estonian description
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    invoices = db.relationship('Invoice', backref='vat_rate_obj', lazy=True)
    
    __table_args__ = (
        db.CheckConstraint('rate >= 0 AND rate <= 100', name='check_vat_rate_valid'),
    )
    
    def __repr__(self):
        return f'<VatRate {self.name}: {self.rate}%>'
    
    @classmethod
    def get_active_rates(cls):
        """Get all active VAT rates ordered by rate."""
        return cls.query.filter_by(is_active=True).order_by(cls.rate.asc()).all()
    
    @classmethod
    def get_default_rate(cls):
        """Get the Estonian standard VAT rate (24%)."""
        return cls.query.filter_by(rate=24.00, is_active=True).first()
    
    @classmethod
    def create_default_rates(cls):
        """Create default Estonian VAT rates."""
        default_rates = [
            {'name': 'Maksuvaba (0%)', 'rate': 0.00, 'description': 'Käibemaksuvaba tooted ja teenused'},
            {'name': 'Vähendatud määr (9%)', 'rate': 9.00, 'description': 'Vähendatud käibemaksumäär'},
            {'name': 'Vähendatud määr (20%)', 'rate': 20.00, 'description': 'Vähendatud käibemaksumäär'},
            {'name': 'Standardmäär (24%)', 'rate': 24.00, 'description': 'Eesti standardne käibemaksumäär'}
        ]
        
        for rate_data in default_rates:
            existing_rate = cls.query.filter_by(rate=rate_data['rate']).first()
            if not existing_rate:
                new_rate = cls(
                    name=rate_data['name'],
                    rate=rate_data['rate'],
                    description=rate_data['description']
                )
                db.session.add(new_rate)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


class Client(db.Model):
    """Client model for storing customer information."""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    registry_code = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    invoices = db.relationship('Invoice', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Client #{self.id}: "{self.name}" ({self.email or "no email"})>'
    
    @property
    def invoice_count(self):
        """Get total number of invoices for this client."""
        return len(self.invoices)
    
    @property
    def last_invoice_date(self):
        """Get the date of the most recent invoice."""
        if self.invoices:
            return max(invoice.date for invoice in self.invoices)
        return None
    
    @property
    def total_revenue(self):
        """Calculate total revenue (all invoices) from this client."""
        return sum(invoice.total for invoice in self.invoices)
    
    @property
    def paid_revenue(self):
        """Calculate paid revenue from this client."""
        return sum(invoice.total for invoice in self.invoices if invoice.status == 'makstud')


class Invoice(db.Model):
    """Invoice model for storing invoice information."""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False, unique=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    vat_rate_id = db.Column(db.Integer, db.ForeignKey('vat_rates.id'), nullable=True)  # Reference to VatRate
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=24)  # Keep for backward compatibility
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='maksmata')  # maksmata, makstud
    payment_terms = db.Column(db.String(50), nullable=True)  # e.g., "14 päeva"
    client_extra_info = db.Column(db.Text, nullable=True)  # Additional client notes
    note = db.Column(db.Text, nullable=True)  # Order/reference/project notes
    note_label_id = db.Column(db.Integer, db.ForeignKey('note_labels.id'), nullable=True)  # Reference to selected note label
    announcements = db.Column(db.Text, nullable=True)  # Info ja Teadaanded
    pdf_template = db.Column(db.String(20), nullable=True, default='standard')  # PDF template preference
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lines = db.relationship('InvoiceLine', backref='invoice', lazy=True, cascade='all, delete-orphan')
    note_label_obj = db.relationship('NoteLabel', foreign_keys=[note_label_id], lazy='select')
    
    __table_args__ = (
        db.CheckConstraint('subtotal >= 0', name='check_subtotal_positive'),
        db.CheckConstraint('total >= 0', name='check_total_positive'),
        db.CheckConstraint('vat_rate >= 0', name='check_vat_rate_positive'),
        db.CheckConstraint("status IN ('maksmata', 'makstud')", name='check_status_valid'),
    )
    
    def __repr__(self):
        return f'<Invoice {self.number}: {self.client.name if self.client else "No Client"} - €{self.total} ({self.status})>'
    
    @property
    def vat_amount(self):
        """Calculate VAT amount with proper decimal rounding."""
        from decimal import Decimal, ROUND_HALF_UP
        
        effective_rate = self.get_effective_vat_rate()
        if self.subtotal is None or effective_rate is None:
            return Decimal('0.00')
        
        subtotal = Decimal(str(self.subtotal))
        rate = Decimal(str(effective_rate))
        
        vat_amount = subtotal * (rate / Decimal('100'))
        return vat_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        return self.due_date < date.today() and self.status == 'maksmata'
    
    @property
    def is_paid(self):
        """Check if invoice is paid."""
        return self.status == 'makstud'
    
    @property
    def status_display(self):
        """Get Estonian display name for status."""
        if self.is_overdue:
            return 'Tähtaeg ületatud'
        elif self.status == 'makstud':
            return 'Makstud'
        else:
            return 'Maksmata'
    
    @property
    def status_color(self):
        """Get Bootstrap color class for status."""
        if self.is_overdue:
            return 'danger'
        elif self.status == 'makstud':
            return 'success'
        else:
            return 'warning'
    
    @property
    def can_be_edited(self):
        """Check if invoice can be edited."""
        return True  # Allow editing all invoices for flexibility
    
    @property
    def can_status_change_to_unpaid(self):
        """Check if status can be changed from paid to unpaid."""
        return True  # Allow all status changes for flexibility
    
    def get_effective_vat_rate(self):
        """Get the effective VAT rate (from VatRate object or fallback to vat_rate column)."""
        if self.vat_rate_obj:
            return self.vat_rate_obj.rate
        return self.vat_rate
    
    def get_preferred_pdf_template(self):
        """Get preferred PDF template for this invoice."""
        if self.pdf_template and self.pdf_template in ['standard', 'modern', 'elegant', 'minimal']:
            return self.pdf_template
        # Fallback to company default
        company_settings = CompanySettings.get_settings()
        return company_settings.default_pdf_template or 'standard'
    
    def calculate_totals(self):
        """Calculate invoice totals from lines."""
        from decimal import Decimal
        self.subtotal = sum(line.line_total for line in self.lines)
        self.total = float(Decimal(str(self.subtotal)) + self.vat_amount)
    
    def mark_as_paid(self):
        """Mark invoice as paid."""
        self.status = 'makstud'
        self.updated_at = datetime.utcnow()
    
    def mark_as_unpaid(self):
        """Mark invoice as unpaid."""
        self.status = 'maksmata'
        self.updated_at = datetime.utcnow()
    
    def update_status_if_overdue(self):
        """Update status to overdue if due date has passed."""
        # No longer needed - overdue is determined dynamically by is_overdue property
        pass
    
    def can_change_status_to(self, new_status):
        """Check if status can be changed to the new status."""
        # Valid status transitions - only 2 statuses now
        valid_statuses = ['maksmata', 'makstud']
        if new_status not in valid_statuses:
            return False, f'Vigane staatus: {new_status}'
        
        # Allow all transitions between the two statuses
        return True, None
    
    def set_status(self, new_status):
        """Set invoice status with validation."""
        can_change, error_message = self.can_change_status_to(new_status)
        if not can_change:
            raise ValueError(error_message)
        
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def update_overdue_invoices(cls):
        """Class method to update all overdue invoices."""
        # No longer needed - overdue status is determined dynamically
        # Return 0 to indicate no updates needed
        return 0
    
    @classmethod
    def migrate_old_statuses(cls):
        """Migrate old status values to new 2-status system."""
        # Mapping from old statuses to new ones
        status_mapping = {
            'mustand': 'maksmata',      # draft -> unpaid
            'saadetud': 'maksmata',     # sent -> unpaid  
            'tähtaeg ületatud': 'maksmata',  # overdue -> unpaid
            'makstud': 'makstud'        # paid -> paid (unchanged)
        }
        
        updated_count = 0
        invoices = cls.query.all()
        
        for invoice in invoices:
            old_status = invoice.status
            if old_status in status_mapping:
                new_status = status_mapping[old_status]
                if old_status != new_status:
                    invoice.status = new_status
                    invoice.updated_at = datetime.utcnow()
                    updated_count += 1
        
        return updated_count


class InvoiceLine(db.Model):
    """Invoice line model for storing individual line items."""
    __tablename__ = 'invoice_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    qty = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    __table_args__ = (
        db.CheckConstraint('qty > 0', name='check_qty_positive'),
        db.CheckConstraint('unit_price >= 0', name='check_unit_price_non_negative'),
        db.CheckConstraint('line_total >= 0', name='check_line_total_non_negative'),
    )
    
    def __repr__(self):
        return f'<InvoiceLine "{self.description[:50]}..." qty={self.qty} price={self.unit_price} total={self.line_total}>'


class PaymentTerms(db.Model):
    """Payment terms model for managing different payment conditions."""
    __tablename__ = 'payment_terms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # e.g., "14 päeva"
    days = db.Column(db.Integer, nullable=False)  # e.g., 14
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentTerms "{self.name}" ({self.days} päeva)>'
    
    @classmethod
    def get_active_terms(cls):
        """Get all active payment terms ordered by days."""
        return cls.query.filter_by(is_active=True).order_by(cls.days.asc()).all()
    
    @classmethod
    def get_default_term(cls):
        """Get the default payment term."""
        return cls.query.filter_by(is_default=True, is_active=True).first()
    
    @classmethod
    def get_choices(cls):
        """Get payment terms choices for forms."""
        terms = cls.get_active_terms()
        return [(term.name, f"{term.days} {'päev' if term.days == 1 else 'päeva'}") for term in terms]
    
    @classmethod
    def create_default_terms(cls):
        """Create default payment terms."""
        default_terms = [
            {'name': '0 päeva', 'days': 0, 'is_default': False},
            {'name': '7 päeva', 'days': 7, 'is_default': False},
            {'name': '14 päeva', 'days': 14, 'is_default': True},
            {'name': '21 päeva', 'days': 21, 'is_default': False},
            {'name': '30 päeva', 'days': 30, 'is_default': False},
            {'name': '60 päeva', 'days': 60, 'is_default': False},
            {'name': '90 päeva', 'days': 90, 'is_default': False},
        ]
        
        for term_data in default_terms:
            existing_term = cls.query.filter_by(name=term_data['name']).first()
            if not existing_term:
                new_term = cls(
                    name=term_data['name'],
                    days=term_data['days'],
                    is_default=term_data['is_default']
                )
                db.session.add(new_term)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


class PenaltyRate(db.Model):
    """Penalty rate model for managing late payment fees."""
    __tablename__ = 'penalty_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # e.g., "0,5% päevas"
    rate_per_day = db.Column(db.Numeric(5, 3), nullable=False)  # e.g., 0.500 for 0.5%
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.CheckConstraint('rate_per_day >= 0 AND rate_per_day <= 10', name='check_penalty_rate_valid'),
    )
    
    def __repr__(self):
        return f'<PenaltyRate {self.name}: {self.rate_per_day}% päevas>'
    
    @classmethod
    def get_active_rates(cls):
        """Get all active penalty rates ordered by rate."""
        return cls.query.filter_by(is_active=True).order_by(cls.rate_per_day.asc()).all()
    
    @classmethod
    def get_default_rate(cls):
        """Get the default penalty rate."""
        return cls.query.filter_by(is_default=True, is_active=True).first()
    
    @classmethod
    def create_default_rates(cls):
        """Create default Estonian penalty rates."""
        default_rates = [
            {'name': '0% päevas', 'rate_per_day': 0.000, 'is_default': False},
            {'name': '0,1% päevas', 'rate_per_day': 0.100, 'is_default': False},
            {'name': '0,2% päevas', 'rate_per_day': 0.200, 'is_default': False},
            {'name': '0,5% päevas', 'rate_per_day': 0.500, 'is_default': True},
            {'name': '1% päevas', 'rate_per_day': 1.000, 'is_default': False},
        ]
        
        for rate_data in default_rates:
            existing_rate = cls.query.filter_by(rate_per_day=rate_data['rate_per_day']).first()
            if not existing_rate:
                new_rate = cls(
                    name=rate_data['name'],
                    rate_per_day=rate_data['rate_per_day'],
                    is_default=rate_data['is_default']
                )
                db.session.add(new_rate)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


class CompanySettings(db.Model):
    """Company settings model for storing business information."""
    __tablename__ = 'company_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False, default='')
    company_address = db.Column(db.Text, default='')
    company_registry_code = db.Column(db.String(50), default='')
    company_vat_number = db.Column(db.String(50), default='')
    company_phone = db.Column(db.String(50), default='')
    company_email = db.Column(db.String(120), default='')
    company_website = db.Column(db.String(255), default='')
    company_logo_url = db.Column(db.String(500), default='')
    # PDF template-specific logos
    logo_standard_url = db.Column(db.String(500), default='')
    logo_modern_url = db.Column(db.String(500), default='')
    logo_elegant_url = db.Column(db.String(500), default='')
    logo_minimal_url = db.Column(db.String(500), default='')
    logo_classic_url = db.Column(db.String(500), default='')
    company_bank = db.Column(db.String(100), default='')
    company_bank_account = db.Column(db.String(50), default='')
    marketing_messages = db.Column(db.Text, default='')
    default_vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=24.00)
    default_vat_rate_id = db.Column(db.Integer, db.ForeignKey('vat_rates.id'), nullable=True)  # Reference to default VAT rate
    default_payment_terms_id = db.Column(db.Integer, db.ForeignKey('payment_terms.id'), nullable=True)  # Reference to default payment terms
    default_penalty_rate_id = db.Column(db.Integer, db.ForeignKey('penalty_rates.id'), nullable=True)  # Reference to default penalty rate
    default_pdf_template = db.Column(db.String(20), nullable=False, default='standard')
    invoice_terms = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    default_vat_rate_obj = db.relationship('VatRate', foreign_keys=[default_vat_rate_id], lazy='select')
    default_payment_terms_obj = db.relationship('PaymentTerms', foreign_keys=[default_payment_terms_id], lazy='select')
    default_penalty_rate_obj = db.relationship('PenaltyRate', foreign_keys=[default_penalty_rate_id], lazy='select')
    
    @classmethod
    def get_settings(cls):
        """Get current company settings (create default if none exist)."""
        settings = cls.query.first()
        if not settings:
            settings = cls(company_name='Minu Ettevõte')
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @classmethod
    def get_payment_terms_choices(cls):
        """Get payment terms options for forms (deprecated - use PaymentTerms.get_choices)."""
        # Fallback to PaymentTerms model
        try:
            return PaymentTerms.get_choices()
        except:
            # Fallback to static choices if PaymentTerms table doesn't exist yet
            return [
                ('0 päeva', '0 päeva'),
                ('7 päeva', '7 päeva'),
                ('14 päeva', '14 päeva'),
                ('21 päeva', '21 päeva'),
                ('30 päeva', '30 päeva'),
                ('60 päeva', '60 päeva'),
                ('90 päeva', '90 päeva'),
            ]
    
    @property
    def default_vat_rate_obj(self):
        """Get the default VAT rate object."""
        if self.default_vat_rate_id:
            return VatRate.query.get(self.default_vat_rate_id)
        # Fallback to finding by rate value
        return VatRate.query.filter_by(rate=self.default_vat_rate, is_active=True).first()
    
    @property
    def default_penalty_rate_obj(self):
        """Get the default penalty rate object."""
        if self.default_penalty_rate_id:
            return PenaltyRate.query.get(self.default_penalty_rate_id)
        # Fallback to default penalty rate
        return PenaltyRate.get_default_rate()
    
    def get_logo_for_template(self, template_id):
        """Get logo URL for specific PDF template, fallback to main logo."""
        template_logo_field = f'logo_{template_id}_url'
        template_logo = getattr(self, template_logo_field, '') if hasattr(self, template_logo_field) else ''
        
        # Return template-specific logo if exists, otherwise return main logo
        return template_logo if template_logo else self.company_logo_url
    
    def set_logo_for_template(self, template_id, logo_url):
        """Set logo URL for specific PDF template."""
        template_logo_field = f'logo_{template_id}_url'
        if hasattr(self, template_logo_field):
            setattr(self, template_logo_field, logo_url)
            db.session.commit()
            return True
        return False
    
    def get_all_template_logos(self):
        """Get all template-specific logos as dictionary."""
        return {
            'standard': self.logo_standard_url,
            'modern': self.logo_modern_url,
            'elegant': self.logo_elegant_url,
            'minimal': self.logo_minimal_url,
            'classic': self.logo_classic_url
        }
    
    def get_logo_for_template_new(self, template_name):
        """Get logo for specific PDF template using new centralized system."""
        # First try new logo assignment system
        logo = TemplateLogoAssignment.get_logo_for_template(self.id, template_name)
        if logo:
            return logo.get_url()
        
        # Fallback to old system (deprecated but maintained for backward compatibility)
        return self.get_logo_for_template(template_name)
    
    def set_logo_for_template_new(self, template_name, logo_id):
        """Set logo for specific template using new centralized system."""
        return TemplateLogoAssignment.set_logo_for_template(self.id, template_name, logo_id)
    
    def remove_logo_for_template_new(self, template_name):
        """Remove logo assignment for specific template using new system."""
        return TemplateLogoAssignment.remove_logo_for_template(self.id, template_name)
    
    def get_all_logo_assignments(self):
        """Get all logo assignments for this company."""
        return TemplateLogoAssignment.get_all_assignments_for_company(self.id)
    
    def migrate_old_logos_to_new_system(self):
        """Migrate old logo URLs to new centralized system."""
        from werkzeug.utils import secure_filename
        import os
        import uuid
        
        migrated_count = 0
        
        # Template mappings
        old_logo_fields = {
            'standard': self.logo_standard_url,
            'modern': self.logo_modern_url, 
            'elegant': self.logo_elegant_url,
            'minimal': self.logo_minimal_url,
            'classic': self.logo_classic_url
        }
        
        # Also check main company logo
        if self.company_logo_url:
            old_logo_fields['main'] = self.company_logo_url
        
        for template_name, logo_url in old_logo_fields.items():
            if logo_url and logo_url.strip():
                # Check if file exists
                if logo_url.startswith('/static/uploads/'):
                    file_path = logo_url.replace('/', '', 1)  # Remove leading slash
                elif logo_url.startswith('static/uploads/'):
                    file_path = logo_url
                else:
                    continue
                
                full_path = file_path
                if os.path.exists(full_path):
                    try:
                        # Get file info
                        file_size = os.path.getsize(full_path)
                        filename = os.path.basename(full_path)
                        
                        # Create Logo entry
                        logo = Logo(
                            filename=filename,
                            original_name=filename,
                            file_path=full_path,
                            file_size=file_size
                        )
                        db.session.add(logo)
                        db.session.flush()  # Get logo.id
                        
                        # Create template assignment (skip 'main' - that's handled differently)
                        if template_name != 'main':
                            TemplateLogoAssignment.set_logo_for_template(
                                self.id, template_name, logo.id
                            )
                        else:
                            # For main logo, we could assign to 'standard' template or handle specially
                            if not self.logo_standard_url:
                                TemplateLogoAssignment.set_logo_for_template(
                                    self.id, 'standard', logo.id
                                )
                        
                        migrated_count += 1
                        
                    except Exception as e:
                        db.session.rollback()
                        continue
        
        if migrated_count > 0:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                migrated_count = 0
        
        return migrated_count
    
    def __repr__(self):
        return f'<CompanySettings "{self.company_name}">'


class Logo(db.Model):
    """Logo model for centralized logo storage."""
    __tablename__ = 'logos'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # Generated unique filename
    original_name = db.Column(db.String(255), nullable=False)  # Original uploaded filename
    file_path = db.Column(db.String(500), nullable=False)  # Full file path
    file_size = db.Column(db.Integer, nullable=False)  # File size in bytes
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    template_assignments = db.relationship('TemplateLogoAssignment', backref='logo', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Logo {self.filename}: {self.original_name}>'
    
    @classmethod
    def get_all_active(cls):
        """Get all active logos ordered by upload date (newest first)."""
        return cls.query.filter_by(is_active=True).order_by(cls.upload_date.desc()).all()
    
    @classmethod
    def get_by_id(cls, logo_id):
        """Get logo by ID."""
        return cls.query.filter_by(id=logo_id, is_active=True).first()
    
    def delete_logo(self):
        """Soft delete logo and remove file."""
        import os
        
        # Remove file from filesystem
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        except Exception:
            pass  # File might already be deleted
        
        # Soft delete from database
        self.is_active = False
        
        # Remove all template assignments
        for assignment in self.template_assignments:
            db.session.delete(assignment)
        
        db.session.commit()
        return True
    
    def get_url(self):
        """Get the URL path for this logo."""
        # Convert file_path to URL (assuming static/uploads structure)
        if self.file_path.startswith('static/'):
            return f"/{self.file_path}"
        return f"/static/uploads/{self.filename}"
    
    @property
    def file_size_mb(self):
        """Get file size in MB for display."""
        return round(self.file_size / (1024 * 1024), 2)


class TemplateLogoAssignment(db.Model):
    """Template-Logo assignment model for managing template-specific logos."""
    __tablename__ = 'template_logo_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    company_settings_id = db.Column(db.Integer, db.ForeignKey('company_settings.id'), nullable=False)
    template_name = db.Column(db.String(50), nullable=False)  # e.g., 'standard', 'modern', 'elegant'
    logo_id = db.Column(db.Integer, db.ForeignKey('logos.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company_settings = db.relationship('CompanySettings', backref='logo_assignments')
    
    __table_args__ = (
        db.UniqueConstraint('company_settings_id', 'template_name', name='unique_company_template_logo'),
    )
    
    def __repr__(self):
        return f'<TemplateLogoAssignment {self.template_name}: Logo#{self.logo_id}>'
    
    @classmethod
    def get_logo_for_template(cls, company_settings_id, template_name):
        """Get logo assigned to specific template for a company."""
        assignment = cls.query.filter_by(
            company_settings_id=company_settings_id,
            template_name=template_name
        ).first()
        
        if assignment and assignment.logo and assignment.logo.is_active:
            return assignment.logo
        return None
    
    @classmethod
    def set_logo_for_template(cls, company_settings_id, template_name, logo_id):
        """Set logo for specific template."""
        # Verify logo exists and is active
        logo = Logo.get_by_id(logo_id)
        if not logo:
            return False
        
        # Find existing assignment or create new one
        assignment = cls.query.filter_by(
            company_settings_id=company_settings_id,
            template_name=template_name
        ).first()
        
        if assignment:
            assignment.logo_id = logo_id
            assignment.updated_at = datetime.utcnow()
        else:
            assignment = cls(
                company_settings_id=company_settings_id,
                template_name=template_name,
                logo_id=logo_id
            )
            db.session.add(assignment)
        
        try:
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False
    
    @classmethod
    def remove_logo_for_template(cls, company_settings_id, template_name):
        """Remove logo assignment for specific template."""
        assignment = cls.query.filter_by(
            company_settings_id=company_settings_id,
            template_name=template_name
        ).first()
        
        if assignment:
            db.session.delete(assignment)
            try:
                db.session.commit()
                return True
            except Exception:
                db.session.rollback()
                return False
        return True  # Already removed
    
    @classmethod
    def get_all_assignments_for_company(cls, company_settings_id):
        """Get all logo assignments for a company."""
        return cls.query.filter_by(company_settings_id=company_settings_id).all()


class NoteLabel(db.Model):
    """Note label model for customizable note field labels in invoices."""
    __tablename__ = 'note_labels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # e.g., "Märkus", "Viitenumber", "Projektinumber"
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<NoteLabel "{self.name}">'
    
    @classmethod
    def get_choices(cls):
        """Get active note labels for form choices."""
        labels = cls.query.filter_by(is_active=True).order_by(cls.name).all()
        return [(label.id, label.name) for label in labels]
    
    @classmethod
    def get_default_label(cls):
        """Get the default note label."""
        default_label = cls.query.filter_by(is_default=True, is_active=True).first()
        if default_label:
            return default_label
        # Fallback to first active label
        first_label = cls.query.filter_by(is_active=True).first()
        if first_label:
            return first_label
        # Create default if none exist
        return cls.create_default_labels()[0]
    
    @classmethod
    def create_default_labels(cls):
        """Create default note labels."""
        default_labels = [
            {'name': 'Märkus', 'is_default': True},
            {'name': 'Viitenumber', 'is_default': False},
            {'name': 'Tellimus', 'is_default': False},
            {'name': 'Projektinumber', 'is_default': False},
            {'name': 'Töönumber', 'is_default': False},
        ]
        
        created_labels = []
        for label_data in default_labels:
            existing_label = cls.query.filter_by(name=label_data['name']).first()
            if not existing_label:
                new_label = cls(
                    name=label_data['name'],
                    is_default=label_data['is_default']
                )
                db.session.add(new_label)
                created_labels.append(new_label)
        
        try:
            db.session.commit()
            return created_labels
        except Exception:
            db.session.rollback()
            raise
    
    @classmethod
    def set_default(cls, label_id):
        """Set a specific label as default."""
        # Remove default from all labels
        cls.query.update({'is_default': False})
        
        # Set new default
        label = cls.query.get(label_id)
        if label:
            label.is_default = True
            db.session.commit()
            return True
        return False