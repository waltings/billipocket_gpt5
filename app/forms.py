from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, DateField, SelectField, FieldList, FormField, HiddenField, IntegerField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length, ValidationError, EqualTo
from datetime import date, timedelta


def validate_unique_invoice_number(form, field):
    """Custom validator to ensure invoice number is unique."""
    from app.models import Invoice
    
    # Get the invoice being edited (if any)
    invoice_id = getattr(form, '_invoice_id', None)
    
    # Check if another invoice already has this number
    existing_invoice = Invoice.query.filter_by(number=field.data).first()
    
    if existing_invoice:
        # If editing an invoice, allow the same number if it belongs to the same invoice
        if invoice_id and existing_invoice.id == invoice_id:
            return  # This is fine - same invoice keeping its number
        else:
            # Another invoice already has this number
            raise ValidationError(f'Arve number "{field.data}" on juba kasutusel.')


def validate_invoice_number_format(form, field):
    """Custom validator to ensure invoice number follows the correct format."""
    import re
    
    if not field.data:
        return
    
    # Expected format: YYYY-NNNN (e.g., 2025-0001)
    if not re.match(r'^\d{4}-\d{4}$', field.data):
        raise ValidationError('Arve number peab olema kujul AAAA-NNNN (näiteks: 2025-0001).')


def validate_status_change(form, field):
    """Custom validator to prevent invalid status changes."""
    from app.models import Invoice
    
    # Get the invoice being edited (if any)
    invoice_id = getattr(form, '_invoice_id', None)
    if not invoice_id:
        return  # New invoice, no restrictions
    
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return  # Invoice not found, let it pass
    
    new_status = field.data
    can_change, error_message = invoice.can_change_status_to(new_status)
    
    if not can_change:
        raise ValidationError(error_message)


class ClientForm(FlaskForm):
    """Form for creating and editing clients."""
    name = StringField('Nimi', validators=[DataRequired(message='Nimi on kohustuslik')])
    registry_code = StringField('Registrikood', validators=[Optional(), Length(max=20)])
    email = StringField('E-post', validators=[Optional(), Email(message='Vigane e-posti aadress')])
    phone = StringField('Telefon', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Aadress', validators=[Optional()])


class InvoiceLineForm(FlaskForm):
    """Form for individual invoice lines."""
    id = HiddenField()
    description = StringField('Kirjeldus', validators=[DataRequired(message='Kirjeldus on kohustuslik')])
    qty = DecimalField('Kogus', validators=[DataRequired(message='Kogus on kohustuslik'), NumberRange(min=0.01, message='Kogus peab olema positiivne')])
    unit_price = DecimalField('Ühiku hind', validators=[DataRequired(message='Ühiku hind on kohustuslik'), NumberRange(min=0, message='Hind ei saa olla negatiivne')])
    line_total = DecimalField('Kokku', validators=[Optional()])


class InvoiceForm(FlaskForm):
    """Form for creating and editing invoices."""
    number = StringField('Arve number', 
                        validators=[
                            DataRequired(message='Arve number on kohustuslik'),
                            validate_invoice_number_format,
                            validate_unique_invoice_number
                        ], 
                        render_kw={"placeholder": "Näiteks: 2025-0001"})
    client_id = SelectField('Klient', validators=[DataRequired(message='Klient on kohustuslik')], coerce=int)
    date = DateField('Arve kuupäev', validators=[DataRequired(message='Arve kuupäev on kohustuslik')], default=date.today)
    due_date = DateField('Maksetähtaeg', validators=[DataRequired(message='Maksetähtaeg on kohustuslik')], 
                        default=lambda: date.today() + timedelta(days=14))
    vat_rate_id = HiddenField('KM määr', validators=[DataRequired(message='KM määr on kohustuslik')])
    payment_terms = SelectField('Makse tingimus', choices=[], validators=[Optional()])
    client_extra_info = TextAreaField('Klienti lisainfo', validators=[Optional()])
    note = TextAreaField('Märkus', validators=[Optional()])
    status = SelectField('Staatus', choices=[
        ('maksmata', 'Maksmata'),
        ('makstud', 'Makstud')
    ], default='maksmata', validators=[validate_status_change])
    pdf_template = SelectField('PDF Mall', choices=[
        ('standard', 'Standard'),
        ('modern', 'Modern'),
        ('elegant', 'Elegant'),
        ('minimal', 'Minimal'),
        ('classic', 'Classic')
    ], default='standard', validators=[Optional()])
    lines = FieldList(FormField(InvoiceLineForm), min_entries=1)
    announcements = TextAreaField('Info ja Teadaanded', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(InvoiceForm, self).__init__(*args, **kwargs)
        # Client choices will be populated in the route
        self.client_id.choices = []
        # Payment terms choices will be populated in the route
        self.payment_terms.choices = []


class InvoiceSearchForm(FlaskForm):
    """Form for searching and filtering invoices."""
    status = SelectField('Staatus', choices=[
        ('', 'Kõik'),
        ('maksmata', 'Maksmata'),
        ('makstud', 'Makstud')
    ], default='')
    client_id = SelectField('Klient', choices=[('', 'Kõik')], coerce=str, default='')
    date_from = DateField('Alates', validators=[Optional()])
    date_to = DateField('Kuni', validators=[Optional()])
    search = StringField('Otsing', validators=[Optional()], render_kw={"placeholder": "Otsi arvet või klienti..."})
    
    def __init__(self, *args, **kwargs):
        super(InvoiceSearchForm, self).__init__(*args, **kwargs)
        # Client choices will be populated in the route
        self.client_id.choices = [('', 'Kõik')]


class ClientSearchForm(FlaskForm):
    """Form for searching clients."""
    search = StringField('Otsing', validators=[Optional()], render_kw={"placeholder": "Otsi klientide seast..."})


class CompanySettingsForm(FlaskForm):
    """Form for company settings."""
    company_name = StringField('Ettevõtte nimi', validators=[DataRequired(message='Ettevõtte nimi on kohustuslik')])
    company_address = TextAreaField('Aadress', validators=[Optional()])
    company_registry_code = StringField('Registrikood', validators=[Optional(), Length(max=50)])
    company_vat_number = StringField('KMKR number', validators=[Optional(), Length(max=50)])
    company_phone = StringField('Telefon', validators=[Optional(), Length(max=50)])
    company_email = StringField('E-post', validators=[Optional(), Email(message='Vigane e-posti aadress')])
    company_website = StringField('Veebileht', validators=[Optional(), Length(max=255)])
    company_logo_url = StringField('Logo URL', validators=[Optional(), Length(max=500)])
    company_bank = StringField('Pank', validators=[Optional(), Length(max=100)])
    company_bank_account = StringField('Pangakonto', validators=[Optional(), Length(max=50)])
    marketing_messages = TextAreaField('Turundussõnumid', validators=[Optional()])
    default_vat_rate_id = SelectField('Vaikimisi KM määr', 
                                     validators=[DataRequired(message='KM määr on kohustuslik')],
                                     coerce=int)
    default_pdf_template = SelectField('Vaikimisi PDF mall', 
                                     choices=[
                                         ('standard', 'Standard'),
                                         ('modern', 'Modern'),
                                         ('elegant', 'Elegant'),
                                         ('minimal', 'Minimal'),
                                         ('classic', 'Classic')
                                     ], 
                                     default='standard',
                                     validators=[DataRequired(message='PDF mall on kohustuslik')])
    default_payment_terms_id = SelectField('Vaikimisi maksetingimus',
                                          validators=[DataRequired(message='Maksetingimus on kohustuslik')],
                                          coerce=int)
    default_penalty_rate_id = SelectField('Vaikimisi viivis',
                                         validators=[DataRequired(message='Viivis on kohustuslik')],
                                         coerce=int)
    invoice_terms = TextAreaField('Arve tingimused', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(CompanySettingsForm, self).__init__(*args, **kwargs)
        # VAT rates, payment terms and penalty rates choices will be populated in the route
        self.default_vat_rate_id.choices = []
        self.default_payment_terms_id.choices = []
        self.default_penalty_rate_id.choices = []


class VatRateForm(FlaskForm):
    """Form for creating and editing VAT rates."""
    name = StringField('Nimetus', validators=[DataRequired(message='Nimetus on kohustuslik'), Length(max=100)])
    rate = DecimalField('Määr (%)', validators=[
        DataRequired(message='KM määr on kohustuslik'), 
        NumberRange(min=0, max=100, message='KM määr peab olema 0-100% vahel')
    ])
    description = StringField('Kirjeldus', validators=[Optional(), Length(max=255)])
    is_active = SelectField('Staatus', choices=[
        (True, 'Aktiivne'),
        (False, 'Mitteaktiivne')
    ], default=True, coerce=lambda x: x == 'True')
    
    def validate_rate(self, field):
        """Ensure the rate is unique when creating or editing."""
        from app.models import VatRate
        
        # Get the VAT rate being edited (if any)
        vat_rate_id = getattr(self, '_vat_rate_id', None)
        
        # Check if another VAT rate already has this rate
        existing_rate = VatRate.query.filter_by(rate=field.data).first()
        
        if existing_rate:
            # If editing a VAT rate, allow the same rate if it belongs to the same record
            if vat_rate_id and existing_rate.id == vat_rate_id:
                return  # This is fine - same rate keeping its value
            else:
                # Another rate already has this percentage
                raise ValidationError(f'KM määr "{field.data}%" on juba olemas.')
    
    def validate_name(self, field):
        """Ensure the name is unique when creating or editing."""
        from app.models import VatRate
        
        # Get the VAT rate being edited (if any)
        vat_rate_id = getattr(self, '_vat_rate_id', None)
        
        # Check if another VAT rate already has this name
        existing_rate = VatRate.query.filter_by(name=field.data).first()
        
        if existing_rate:
            # If editing a VAT rate, allow the same name if it belongs to the same record
            if vat_rate_id and existing_rate.id == vat_rate_id:
                return  # This is fine - same rate keeping its name
            else:
                # Another rate already has this name
                raise ValidationError(f'Nimetus "{field.data}" on juba kasutusel.')


class PaymentTermsForm(FlaskForm):
    """Form for creating and editing payment terms."""
    name = StringField('Nimetus', validators=[DataRequired(message='Nimetus on kohustuslik'), Length(max=50)])
    days = IntegerField('Päevade arv', validators=[
        DataRequired(message='Päevade arv on kohustuslik'),
        NumberRange(min=0, max=365, message='Päevade arv peab olema 0-365 vahel')
    ])
    is_default = BooleanField('Vaikimisi tingimus')
    is_active = BooleanField('Aktiivne', default=True)
    
    def validate_name(self, field):
        """Ensure the name is unique when creating or editing."""
        from app.models import PaymentTerms
        
        # Get the payment term being edited (if any)
        payment_term_id = getattr(self, '_payment_term_id', None)
        
        # Check if another payment term already has this name
        existing_term = PaymentTerms.query.filter_by(name=field.data).first()
        
        if existing_term:
            # If editing a payment term, allow the same name if it belongs to the same record
            if payment_term_id and existing_term.id == payment_term_id:
                return  # This is fine - same term keeping its name
            else:
                # Another term already has this name
                raise ValidationError(f'Nimetus "{field.data}" on juba kasutusel.')
    
    def validate_days(self, field):
        """Ensure the days value is unique when creating or editing."""
        from app.models import PaymentTerms
        
        # Get the payment term being edited (if any)
        payment_term_id = getattr(self, '_payment_term_id', None)
        
        # Check if another payment term already has this days value
        existing_term = PaymentTerms.query.filter_by(days=field.data).first()
        
        if existing_term:
            # If editing a payment term, allow the same days if it belongs to the same record
            if payment_term_id and existing_term.id == payment_term_id:
                return  # This is fine - same term keeping its days
            else:
                # Another term already has this days value
                raise ValidationError(f'Päevade arv "{field.data}" on juba kasutusel.')
    
    def validate_is_default(self, field):
        """Ensure only one default payment term exists."""
        from app.models import PaymentTerms
        
        if field.data:  # If setting as default
            # Get the payment term being edited (if any)
            payment_term_id = getattr(self, '_payment_term_id', None)
            
            # Check if there's already a default term
            existing_default = PaymentTerms.query.filter_by(is_default=True).first()
            
            if existing_default:
                # If editing a payment term, allow if it's the same record
                if payment_term_id and existing_default.id == payment_term_id:
                    return  # This is fine - same term staying as default
                else:
                    # Another term is already default
                    raise ValidationError(f'Vaikimisi tingimus on juba määratud: "{existing_default.name}".')


class PaymentTermsManagementForm(FlaskForm):
    """Form for managing multiple payment terms in settings."""
    pass  # This will be dynamically populated with payment terms


class PenaltyRateForm(FlaskForm):
    """Form for creating and editing penalty rates."""
    name = StringField('Nimetus', validators=[DataRequired(message='Nimetus on kohustuslik'), Length(max=100)])
    rate_per_day = DecimalField('Määr päevas (%)', validators=[
        DataRequired(message='Viivise määr on kohustuslik'), 
        NumberRange(min=0, max=10, message='Viivise määr peab olema 0-10% vahel')
    ])
    is_default = BooleanField('Vaikimisi viivis')
    is_active = BooleanField('Aktiivne', default=True)
    
    def validate_name(self, field):
        """Ensure the name is unique when creating or editing."""
        from app.models import PenaltyRate
        
        # Get the penalty rate being edited (if any)
        penalty_rate_id = getattr(self, '_penalty_rate_id', None)
        
        # Check if another penalty rate already has this name
        existing_rate = PenaltyRate.query.filter_by(name=field.data).first()
        
        if existing_rate:
            # If editing a penalty rate, allow the same name if it belongs to the same record
            if penalty_rate_id and existing_rate.id == penalty_rate_id:
                return  # This is fine - same rate keeping its name
            else:
                # Another rate already has this name
                raise ValidationError(f'Nimetus "{field.data}" on juba kasutusel.')
    
    def validate_rate_per_day(self, field):
        """Ensure the rate is unique when creating or editing."""
        from app.models import PenaltyRate
        
        # Get the penalty rate being edited (if any)
        penalty_rate_id = getattr(self, '_penalty_rate_id', None)
        
        # Check if another penalty rate already has this rate
        existing_rate = PenaltyRate.query.filter_by(rate_per_day=field.data).first()
        
        if existing_rate:
            # If editing a penalty rate, allow the same rate if it belongs to the same record
            if penalty_rate_id and existing_rate.id == penalty_rate_id:
                return  # This is fine - same rate keeping its value
            else:
                # Another rate already has this percentage
                raise ValidationError(f'Viivise määr "{field.data}%" on juba olemas.')
    
    def validate_is_default(self, field):
        """Ensure only one default penalty rate exists."""
        from app.models import PenaltyRate
        
        if field.data:  # If setting as default
            # Get the penalty rate being edited (if any)
            penalty_rate_id = getattr(self, '_penalty_rate_id', None)
            
            # Check if there's already a default rate
            existing_default = PenaltyRate.query.filter_by(is_default=True).first()
            
            if existing_default:
                # If editing a penalty rate, allow if it's the same record
                if penalty_rate_id and existing_default.id == penalty_rate_id:
                    return  # This is fine - same rate staying as default
                else:
                    # Another rate is already default
                    raise ValidationError(f'Vaikimisi viivis on juba määratud: "{existing_default.name}".')


class NoteLabelForm(FlaskForm):
    """Form for managing note labels."""
    name = StringField('Märkuse silt', validators=[
        DataRequired(message='Märkuse silt on kohustuslik'),
        Length(min=1, max=50, message='Märkuse silt peab olema 1-50 tähemärki')
    ])
    is_default = BooleanField('Vaikimisi märkuse silt')
    
    def __init__(self, *args, **kwargs):
        super(NoteLabelForm, self).__init__(*args, **kwargs)
        self._note_label_id = kwargs.get('note_label_id', None)
    
    def validate_name(self, field):
        """Validate that note label name is unique."""
        from app.models import NoteLabel
        
        # Check for existing label with same name
        existing_label = NoteLabel.query.filter_by(name=field.data).first()
        
        if existing_label:
            # If editing a label, allow if it's the same record
            if self._note_label_id and existing_label.id == self._note_label_id:
                return  # This is fine - same label keeping same name
            else:
                raise ValidationError(f'Märkuse silt "{field.data}" on juba olemas.')
    
    def validate_is_default(self, field):
        """Validate default note label selection."""
        from app.models import NoteLabel
        
        if field.data:  # If setting as default
            # Get the note label being edited (if any)
            note_label_id = getattr(self, '_note_label_id', None)
            
            # Check if there's already a default label
            existing_default = NoteLabel.query.filter_by(is_default=True).first()
            
            if existing_default:
                # If editing a note label, allow if it's the same record
                if note_label_id and existing_default.id == note_label_id:
                    return  # This is fine - same label staying as default
                else:
                    # Another label is already default
                    raise ValidationError(f'Vaikimisi märkuse silt on juba määratud: "{existing_default.name}".')


class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Kasutajanimi', validators=[
        DataRequired(message='Kasutajanimi on kohustuslik')
    ])
    password = PasswordField('Parool', validators=[
        DataRequired(message='Parool on kohustuslik')
    ])
    remember_me = BooleanField('Jäta mind meelde')
    
    def validate_username(self, field):
        """Validate that user exists and is active."""
        from app.models import User
        user = User.get_by_username(field.data)
        if not user:
            raise ValidationError('Vigane kasutajanimi või parool.')
    
    def validate_login(self):
        """Validate entire login form."""
        from app.models import User
        
        if not self.validate():
            return False
        
        user = User.get_by_username(self.username.data)
        if not user or not user.check_password(self.password.data):
            self.password.errors.append('Vigane kasutajanimi või parool.')
            return False
        
        self.user = user
        return True


class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Kasutajanimi', validators=[
        DataRequired(message='Kasutajanimi on kohustuslik'),
        Length(min=3, max=80, message='Kasutajanimi peab olema 3-80 tähemärki')
    ])
    email = StringField('E-post', validators=[
        DataRequired(message='E-posti aadress on kohustuslik'),
        Email(message='Vigane e-posti aadress')
    ])
    password = PasswordField('Parool', validators=[
        DataRequired(message='Parool on kohustuslik'),
        Length(min=8, message='Parool peab olema vähemalt 8 tähemärki')
    ])
    password2 = PasswordField('Korda parooli', validators=[
        DataRequired(message='Palun korda parooli'),
        EqualTo('password', message='Paroolid ei kattu')
    ])
    
    def validate_username(self, field):
        """Ensure username is unique."""
        from app.models import User
        user = User.query.filter_by(username=field.data).first()
        if user:
            raise ValidationError(f'Kasutajanimi "{field.data}" on juba kasutusel.')
    
    def validate_email(self, field):
        """Ensure email is unique."""
        from app.models import User
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError(f'E-posti aadress "{field.data}" on juba kasutusel.')


class ChangePasswordForm(FlaskForm):
    """Form for changing password."""
    current_password = PasswordField('Praegune parool', validators=[
        DataRequired(message='Praegune parool on kohustuslik')
    ])
    new_password = PasswordField('Uus parool', validators=[
        DataRequired(message='Uus parool on kohustuslik'),
        Length(min=8, message='Parool peab olema vähemalt 8 tähemärki')
    ])
    new_password2 = PasswordField('Korda uut parooli', validators=[
        DataRequired(message='Palun korda uut parooli'),
        EqualTo('new_password', message='Paroolid ei kattu')
    ])
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
    
    def validate_current_password(self, field):
        """Validate current password."""
        if not self.user.check_password(field.data):
            raise ValidationError('Praegune parool on vale.')


class UserProfileForm(FlaskForm):
    """Form for editing user profile."""
    username = StringField('Kasutajanimi', validators=[
        DataRequired(message='Kasutajanimi on kohustuslik'),
        Length(min=3, max=80, message='Kasutajanimi peab olema 3-80 tähemärki')
    ])
    email = StringField('E-post', validators=[
        DataRequired(message='E-posti aadress on kohustuslik'),
        Email(message='Vigane e-posti aadress')
    ])
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
    
    def validate_username(self, field):
        """Ensure username is unique (except for current user)."""
        from app.models import User
        if field.data != self.user.username:
            user = User.query.filter_by(username=field.data).first()
            if user:
                raise ValidationError(f'Kasutajanimi "{field.data}" on juba kasutusel.')
    
    def validate_email(self, field):
        """Ensure email is unique (except for current user)."""
        from app.models import User
        if field.data != self.user.email:
            user = User.query.filter_by(email=field.data).first()
            if user:
                raise ValidationError(f'E-posti aadress "{field.data}" on juba kasutusel.')