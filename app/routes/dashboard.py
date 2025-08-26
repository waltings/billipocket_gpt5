from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_wtf.csrf import CSRFProtect
from app.models import db, Invoice, Client, VatRate, PaymentTerms, PenaltyRate, NoteLabel, CompanySettings, Logo, TemplateLogoAssignment
from app.logging_config import get_logger
from sqlalchemy import func, case
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from werkzeug.utils import secure_filename
import uuid

logger = get_logger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def overview():
    """Overview/dashboard page with metrics from real data."""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Update overdue invoices first
    updated_count = Invoice.update_overdue_invoices()
    if updated_count > 0:
        db.session.commit()
    
    # Calculate metrics
    # 1. Revenue for current month (paid invoices only)
    revenue_month = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.date >= current_month_start,
        Invoice.status.in_(['makstud'])
    ).scalar() or Decimal('0')
    
    # 2. Total cash received (all paid invoices)
    cash_in = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.status == 'makstud'
    ).scalar() or Decimal('0')
    
    # 3. Number of unpaid invoices (maksmata status - includes overdue via is_overdue property)
    unpaid_count = Invoice.query.filter(
        Invoice.status == 'maksmata'
    ).count()
    
    # 4. Average days to payment (calculated from paid invoices)
    paid_invoices = Invoice.query.filter(Invoice.status == 'makstud').all()
    if paid_invoices:
        total_days = 0
        for invoice in paid_invoices:
            # Assume updated_at is when it was marked as paid
            # For now, use a default of 14 days or calculate from due_date
            days_diff = (invoice.due_date - invoice.date).days
            total_days += max(1, days_diff)  # At least 1 day
        avg_days = total_days // len(paid_invoices)
    else:
        avg_days = 0
    
    # Additional metrics for dashboard
    # Total clients
    total_clients = Client.query.count()
    
    # Total invoices
    total_invoices = Invoice.query.count()
    
    # Outstanding amount (unpaid invoices)
    outstanding = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.status == 'maksmata'
    ).scalar() or Decimal('0')
    
    # Recent invoices for dashboard display
    recent_invoices = Invoice.query.join(Client).order_by(
        Invoice.date.desc()
    ).limit(5).all()
    
    recent_invoices_data = []
    for invoice in recent_invoices:
        # Calculate days to due date
        days_to_due = None
        due_date_str = None
        if invoice.due_date:
            days_to_due = (invoice.due_date - today).days
            due_date_str = invoice.due_date.strftime('%Y-%m-%d')
        
        recent_invoices_data.append({
            'no': invoice.number,
            'date': invoice.date.strftime('%Y-%m-%d'),
            'due_date': due_date_str,
            'days_to_due': days_to_due,
            'client': invoice.client.name,
            'total': float(invoice.total),
            'status': invoice.status,
            'status_display': invoice.status_display
        })
    
    # Overdue invoices
    overdue_invoices = Invoice.query.join(Client).filter(
        Invoice.due_date < today,
        Invoice.status == 'maksmata'
    ).order_by(Invoice.due_date.asc()).all()
    
    overdue_count = len(overdue_invoices)
    overdue_amount = sum(float(invoice.total) for invoice in overdue_invoices)
    
    overdue_invoices_data = []
    for invoice in overdue_invoices[:5]:  # Show max 5 in dashboard
        days_overdue = (today - invoice.due_date).days
        overdue_invoices_data.append({
            'no': invoice.number,
            'due_date': invoice.due_date.strftime('%Y-%m-%d'),
            'client': invoice.client.name,
            'total': float(invoice.total),
            'days_overdue': days_overdue
        })
    
    # Monthly revenue data for chart (last 12 months)
    monthly_revenue_data = []
    monthly_labels = []
    for i in range(11, -1, -1):  # Last 12 months, newest first
        month_start = date(today.year, today.month, 1) - timedelta(days=i*30)  # Approximate month calculation
        # More precise month calculation
        if today.month - i <= 0:
            month_year = today.year - 1
            month_num = today.month - i + 12
        else:
            month_year = today.year
            month_num = today.month - i
        
        month_start = date(month_year, month_num, 1)
        
        # Calculate next month start
        if month_num == 12:
            next_month_start = date(month_year + 1, 1, 1)
        else:
            next_month_start = date(month_year, month_num + 1, 1)
        
        # Get revenue for this month (all invoices, not just paid)
        month_revenue = db.session.query(func.sum(Invoice.total)).filter(
            Invoice.date >= month_start,
            Invoice.date < next_month_start
        ).scalar() or Decimal('0')
        
        monthly_revenue_data.append(float(month_revenue))
        # Estonian month names (abbreviated)
        month_names = ['Jan', 'Veeb', 'Mär', 'Apr', 'Mai', 'Jun', 
                      'Jul', 'Aug', 'Sept', 'Okt', 'Nov', 'Dets']
        month_label = f"{month_names[month_num - 1]} {month_year % 100:02d}"
        monthly_labels.append(month_label)
    
    # Invoice status breakdown for pie chart
    paid_invoices_count = Invoice.query.filter_by(status='makstud').count()
    unpaid_invoices_count = Invoice.query.filter_by(status='maksmata').count()
    
    # Further break down unpaid invoices
    unpaid_not_overdue = unpaid_invoices_count - overdue_count
    
    status_data = {
        'paid': paid_invoices_count,
        'unpaid_not_overdue': unpaid_not_overdue,
        'overdue': overdue_count
    }
    
    status_labels = ['Makstud', 'Maksmata', 'Tähtaeg ületatud']
    status_values = [paid_invoices_count, unpaid_not_overdue, overdue_count]
    status_colors = ['#28a745', '#ffc107', '#dc3545']  # green, yellow, red
    
    # Top customers data (by total invoice amount)
    top_customers_query = db.session.query(
        Client.name,
        func.sum(Invoice.total).label('total_amount')
    ).join(Invoice).group_by(Client.id, Client.name).order_by(
        func.sum(Invoice.total).desc()
    ).limit(10).all()
    
    top_customers_labels = []
    top_customers_data = []
    for customer in top_customers_query:
        top_customers_labels.append(customer.name)
        top_customers_data.append(float(customer.total_amount))
    
    metrics = {
        "revenue_month": float(revenue_month),
        "cash_in": float(cash_in),
        "unpaid": unpaid_count,
        "avg_days": avg_days,
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "outstanding": float(outstanding),
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "monthly_revenue_data": monthly_revenue_data,
        "monthly_labels": monthly_labels,
        "status_labels": status_labels,
        "status_values": status_values,
        "status_colors": status_colors,
        "top_customers_labels": top_customers_labels,
        "top_customers_data": top_customers_data
    }
    
    return render_template('overview.html', 
                         metrics=metrics, 
                         recent_invoices=recent_invoices_data,
                         overdue_invoices=overdue_invoices_data)


@dashboard_bp.route('/reports')
def reports():
    """Reports page."""
    return render_template('reports.html')


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page."""
    from app.models import CompanySettings
    from app.forms import CompanySettingsForm
    
    # Get current settings
    company_settings = CompanySettings.get_settings()
    
    # Create form WITHOUT obj parameter to avoid conflicts
    form = CompanySettingsForm()
    
    # Manually populate form fields from company_settings (avoiding WTForms obj conflicts)
    if request.method == 'GET':
        form.company_name.data = company_settings.company_name
        form.company_address.data = company_settings.company_address
        form.company_registry_code.data = company_settings.company_registry_code
        form.company_vat_number.data = company_settings.company_vat_number
        form.company_phone.data = company_settings.company_phone
        form.company_email.data = company_settings.company_email
        form.company_website.data = company_settings.company_website
        form.company_logo_url.data = company_settings.company_logo_url
        form.company_bank.data = company_settings.company_bank
        form.company_bank_account.data = company_settings.company_bank_account
        form.marketing_messages.data = company_settings.marketing_messages
        form.default_pdf_template.data = company_settings.default_pdf_template
        form.invoice_terms.data = company_settings.invoice_terms
    
    # Populate VAT rate choices
    vat_rates = VatRate.get_active_rates()
    form.default_vat_rate_id.choices = [(rate.id, f"{rate.rate}%") for rate in vat_rates]
    
    # Set current VAT rate selection (only on GET request)
    if request.method == 'GET':
        if company_settings.default_vat_rate_id:
            form.default_vat_rate_id.data = company_settings.default_vat_rate_id
        elif vat_rates:
            # Try to find matching rate by value
            matching_rate = next((r for r in vat_rates if r.rate == company_settings.default_vat_rate), None)
            if matching_rate:
                form.default_vat_rate_id.data = matching_rate.id
            else:
                form.default_vat_rate_id.data = vat_rates[0].id
    
    # Populate payment terms choices
    try:
        payment_terms = PaymentTerms.get_active_terms()
        form.default_payment_terms_id.choices = [(term.id, f"{term.days} {'päev' if term.days == 1 else 'päeva'}") for term in payment_terms]
        
        # Set current payment terms selection (only on GET request)
        if request.method == 'GET':
            if company_settings.default_payment_terms_id:
                form.default_payment_terms_id.data = company_settings.default_payment_terms_id
            else:
                # Try to find default term
                default_term = PaymentTerms.get_default_term()
                if default_term:
                    form.default_payment_terms_id.data = default_term.id
                elif payment_terms:
                    form.default_payment_terms_id.data = payment_terms[0].id
    except Exception as e:
        logger.error(f"Error setting payment terms: {e}")
        # Fallback if PaymentTerms table doesn't exist
        form.default_payment_terms_id.choices = [(1, '14 päeva')]
        form.default_payment_terms_id.data = 1
    
    # Populate penalty rates choices
    try:
        penalty_rates = PenaltyRate.get_active_rates()
        form.default_penalty_rate_id.choices = [(rate.id, rate.name) for rate in penalty_rates]
        
        # Set current penalty rate selection (only on GET request)
        if request.method == 'GET':
            if company_settings.default_penalty_rate_id:
                form.default_penalty_rate_id.data = company_settings.default_penalty_rate_id
            else:
                # Try to find default penalty rate
                default_penalty = PenaltyRate.get_default_rate()
                if default_penalty:
                    form.default_penalty_rate_id.data = default_penalty.id
                elif penalty_rates:
                    form.default_penalty_rate_id.data = penalty_rates[0].id
    except Exception as e:
        logger.error(f"Error setting penalty rates: {e}")
        # Fallback if PenaltyRate table doesn't exist
        form.default_penalty_rate_id.choices = [(1, '0,5% päevas')]
        form.default_penalty_rate_id.data = 1
    
    if form.validate_on_submit():
        # Update settings from form
        company_settings.company_name = form.company_name.data
        company_settings.company_address = form.company_address.data
        company_settings.company_registry_code = form.company_registry_code.data
        company_settings.company_vat_number = form.company_vat_number.data
        company_settings.company_phone = form.company_phone.data
        company_settings.company_email = form.company_email.data
        company_settings.company_website = form.company_website.data
        company_settings.company_logo_url = form.company_logo_url.data
        company_settings.company_bank = form.company_bank.data
        company_settings.company_bank_account = form.company_bank_account.data
        company_settings.marketing_messages = form.marketing_messages.data
        
        # Update VAT rate
        if form.default_vat_rate_id.data:
            selected_vat_rate = VatRate.query.get(form.default_vat_rate_id.data)
            if selected_vat_rate:
                company_settings.default_vat_rate_id = selected_vat_rate.id
                company_settings.default_vat_rate = selected_vat_rate.rate
        
        # Update payment terms default
        if form.default_payment_terms_id.data:
            try:
                # Remove default from all payment terms
                PaymentTerms.query.update({'is_default': False})
                # Set new default
                selected_payment_term = PaymentTerms.query.get(form.default_payment_terms_id.data)
                if selected_payment_term:
                    selected_payment_term.is_default = True
                    company_settings.default_payment_terms_id = selected_payment_term.id
            except:
                pass  # Ignore if PaymentTerms table doesn't exist
        
        # Update penalty rate default
        if form.default_penalty_rate_id.data:
            try:
                # Remove default from all penalty rates
                PenaltyRate.query.update({'is_default': False})
                # Set new default
                selected_penalty_rate = PenaltyRate.query.get(form.default_penalty_rate_id.data)
                if selected_penalty_rate:
                    selected_penalty_rate.is_default = True
                    company_settings.default_penalty_rate_id = selected_penalty_rate.id
            except:
                pass  # Ignore if PenaltyRate table doesn't exist
        
        company_settings.default_pdf_template = form.default_pdf_template.data
        company_settings.invoice_terms = form.invoice_terms.data
        
        # Handle note label default setting from form
        note_label_id = request.form.get('default_note_label_id')
        if note_label_id:
            try:
                # Set new default note label
                NoteLabel.set_default(int(note_label_id))
                logger.info(f"Set default note label to ID: {note_label_id}")
            except Exception as e:
                logger.error(f"Error setting default note label: {e}")
        
        try:
            db.session.commit()
            flash('Ettevõtte seaded on edukalt salvestatud.', 'success')
            return redirect(url_for('dashboard.settings'))
        except Exception as e:
            db.session.rollback()
            flash('Seadete salvestamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    # Get VAT rates and payment terms for management sections
    all_vat_rates = VatRate.query.order_by(VatRate.rate.asc()).all()
    
    try:
        all_payment_terms = PaymentTerms.query.order_by(PaymentTerms.days.asc()).all()
    except:
        all_payment_terms = []
    
    # Get penalty rates for management sections
    try:
        all_penalty_rates = PenaltyRate.query.order_by(PenaltyRate.rate_per_day.asc()).all()
    except:
        all_penalty_rates = []
    
    # Get note labels for management sections
    try:
        note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
        note_label_choices = [(label.id, label.name) for label in note_labels]
        
        # Get default note label
        default_note_label = NoteLabel.get_default_label()
        default_note_label_id = default_note_label.id if default_note_label else None
        
        # Create default labels if none exist
        if not note_labels:
            NoteLabel.create_default_labels()
            note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
            note_label_choices = [(label.id, label.name) for label in note_labels]
            default_note_label = NoteLabel.get_default_label()
            default_note_label_id = default_note_label.id if default_note_label else None
            
    except Exception as e:
        logger.error(f"Error getting note labels: {e}")
        note_label_choices = [(1, 'Märkus')]
        default_note_label_id = 1
    
    return render_template('settings.html', 
                         form=form, 
                         settings=company_settings,
                         all_vat_rates=all_vat_rates,
                         all_payment_terms=all_payment_terms,
                         all_penalty_rates=all_penalty_rates,
                         note_label_choices=note_label_choices,
                         default_note_label_id=default_note_label_id)


@dashboard_bp.route('/settings/upload-logo', methods=['POST'])
def upload_logo():
    """Handle logo file upload."""
    if 'logo' not in request.files:
        return jsonify({'success': False, 'message': 'Fail puudub'}), 400
    
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Fail ei ole valitud'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'svg', 'gif'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'success': False, 'message': 'Lubatud failiformaadid: PNG, JPG, SVG'}), 400
    
    # Validate file size (2MB max)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 2 * 1024 * 1024:  # 2MB
        return jsonify({'success': False, 'message': 'Faili suurus on liiga suur (max 2MB)'}), 400
    
    try:
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Ensure uploads directory exists
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        filepath = os.path.join(upload_dir, unique_filename)
        file.save(filepath)
        
        # Return URL for the uploaded file
        logo_url = f"/static/uploads/{unique_filename}"
        
        return jsonify({
            'success': True, 
            'message': 'Logo edukalt üles laaditud',
            'url': logo_url
        })
        
    except Exception as e:
        logger.error(f"Error uploading logo: {str(e)}")
        return jsonify({'success': False, 'message': 'Faili üleslaadimisel tekkis viga'}), 500


# New Centralized Logo Management API Endpoints

@dashboard_bp.route('/settings/logos', methods=['GET'])
def get_logos():
    """Get all active logos."""
    try:
        logos = Logo.get_all_active()
        company_settings = CompanySettings.get_settings()
        
        # Get current template assignments
        assignments = company_settings.get_all_logo_assignments()
        assignment_dict = {a.template_name: a.logo_id for a in assignments}
        
        logos_data = []
        for logo in logos:
            logos_data.append({
                'id': logo.id,
                'filename': logo.filename,
                'original_name': logo.original_name,
                'url': logo.get_url(),
                'file_size': logo.file_size,
                'file_size_mb': logo.file_size_mb,
                'upload_date': logo.upload_date.strftime('%Y-%m-%d %H:%M'),
                'templates_assigned': [template for template, logo_id in assignment_dict.items() if logo_id == logo.id]
            })
        
        return jsonify({
            'success': True,
            'logos': logos_data
        })
    
    except Exception as e:
        logger.error(f"Error getting logos: {str(e)}")
        return jsonify({'success': False, 'message': 'Logode laadmisel tekkis viga'}), 500


@dashboard_bp.route('/settings/logos/upload', methods=['POST'])
def upload_logo_new():
    """Handle new logo file upload to centralized system."""
    if 'logo' not in request.files:
        return jsonify({'success': False, 'message': 'Fail puudub'}), 400
    
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Fail ei ole valitud'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'svg', 'gif'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'success': False, 'message': 'Lubatud failiformaadid: PNG, JPG, JPEG, SVG, GIF'}), 400
    
    # Validate file size (2MB max)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 2 * 1024 * 1024:  # 2MB
        return jsonify({'success': False, 'message': 'Faili suurus on liiga suur (max 2MB)'}), 400
    
    try:
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Ensure uploads directory exists
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)
        
        # Create Logo database entry
        logo = Logo(
            filename=unique_filename,
            original_name=original_filename,
            file_path=file_path,
            file_size=file_size
        )
        
        db.session.add(logo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Logo edukalt üles laaditud',
            'logo': {
                'id': logo.id,
                'filename': logo.filename,
                'original_name': logo.original_name,
                'url': logo.get_url(),
                'file_size_mb': logo.file_size_mb
            }
        })
        
    except Exception as e:
        logger.error(f"Error uploading logo: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Faili üleslaadimisel tekkis viga'}), 500


@dashboard_bp.route('/settings/logos/<int:logo_id>', methods=['DELETE', 'POST'])
def delete_logo(logo_id):
    """Delete a logo."""
    try:
        # Handle both DELETE and POST methods (POST for CSRF compatibility)
        if request.method == 'POST':
            # Check if it's a delete operation via hidden field or method override
            method_override = request.form.get('_method') or request.headers.get('X-HTTP-Method-Override')
            if method_override != 'DELETE':
                return jsonify({'success': False, 'message': 'Vigane meetod'}), 405
        
        logo = Logo.get_by_id(logo_id)
        if not logo:
            return jsonify({'success': False, 'message': 'Logo ei leitud'}), 404
        
        # Delete logo (soft delete + remove file)
        success = logo.delete_logo()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Logo edukalt kustutatud'
            })
        else:
            return jsonify({'success': False, 'message': 'Logo kustutamisel tekkis viga'}), 500
    
    except Exception as e:
        logger.error(f"Error deleting logo {logo_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Logo kustutamisel tekkis viga'}), 500


@dashboard_bp.route('/settings/templates/<template>/logo/<int:logo_id>', methods=['POST'])
def assign_template_logo(template, logo_id):
    """Assign logo to specific template."""
    try:
        # Validate template name
        valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
        if template not in valid_templates:
            return jsonify({'success': False, 'message': 'Vigane template nimi'}), 400
        
        # Verify logo exists
        logo = Logo.get_by_id(logo_id)
        if not logo:
            return jsonify({'success': False, 'message': 'Logo ei leitud'}), 404
        
        # Set logo for template
        company_settings = CompanySettings.get_settings()
        success = company_settings.set_logo_for_template_new(template, logo_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Logo määratud {template} mallile',
                'template': template,
                'logo': {
                    'id': logo.id,
                    'filename': logo.filename,
                    'url': logo.get_url()
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Logo määramisel tekkis viga'}), 500
    
    except Exception as e:
        logger.error(f"Error assigning logo {logo_id} to template {template}: {str(e)}")
        return jsonify({'success': False, 'message': 'Logo määramisel tekkis viga'}), 500


@dashboard_bp.route('/settings/templates/<template>/logo', methods=['DELETE'])
def remove_template_logo_new(template):
    """Remove logo assignment from specific template."""
    try:
        # Validate template name
        valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
        if template not in valid_templates:
            return jsonify({'success': False, 'message': 'Vigane template nimi'}), 400
        
        # Remove logo assignment
        company_settings = CompanySettings.get_settings()
        success = company_settings.remove_logo_for_template_new(template)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Logo eemaldatud {template} mallilt'
            })
        else:
            return jsonify({'success': False, 'message': 'Logo eemaldamisel tekkis viga'}), 500
    
    except Exception as e:
        logger.error(f"Error removing logo from template {template}: {str(e)}")
        return jsonify({'success': False, 'message': 'Logo eemaldamisel tekkis viga'}), 500


@dashboard_bp.route('/settings/logos/<int:logo_id>/rename', methods=['PATCH'])
def rename_logo(logo_id):
    """Rename a logo."""
    try:
        logo = Logo.get_by_id(logo_id)
        if not logo:
            return jsonify({'success': False, 'message': 'Logo ei leitud'}), 404
        
        data = request.get_json()
        new_name = data.get('name', '').strip() if data else ''
        
        if not new_name:
            return jsonify({'success': False, 'message': 'Logo nimi on kohustuslik'}), 400
        
        if len(new_name) > 255:
            return jsonify({'success': False, 'message': 'Logo nimi on liiga pikk (max 255 tähemärki)'}), 400
        
        # Update logo name
        logo.original_name = new_name
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Logo nimi muudetud: "{new_name}"'
        })
    
    except Exception as e:
        logger.error(f"Error renaming logo {logo_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Viga logo ümbernimetamisel'}), 500


@dashboard_bp.route('/settings/logos/migrate', methods=['POST'])
def migrate_old_logos():
    """Migrate old logo system to new centralized system."""
    try:
        company_settings = CompanySettings.get_settings()
        migrated_count = company_settings.migrate_old_logos_to_new_system()
        
        return jsonify({
            'success': True,
            'message': f'Migreeriti {migrated_count} logo(t) uude süsteemi',
            'migrated_count': migrated_count
        })
    
    except Exception as e:
        logger.error(f"Error migrating old logos: {str(e)}")
        return jsonify({'success': False, 'message': 'Logode migratsiooni tekkis viga'}), 500


@dashboard_bp.route('/settings/vat-rates')
def vat_rates():
    """VAT rates management page."""
    vat_rates = VatRate.query.order_by(VatRate.rate.asc()).all()
    return render_template('vat_rates.html', vat_rates=vat_rates)


@dashboard_bp.route('/settings/vat-rates/new', methods=['GET', 'POST'])
def new_vat_rate():
    """Create new VAT rate."""
    if request.method == 'POST' and request.is_json:
        # Handle AJAX request from modal
        data = request.get_json()
        
        try:
            # Validate input
            rate = float(data.get('rate', 0))
            is_active = data.get('is_active', True)
            
            if rate < 0 or rate > 100:
                return jsonify({'success': False, 'message': 'KM määr peab olema 0-100% vahel'})
            
            # Check for duplicates (only by rate)
            existing_rate = VatRate.query.filter_by(rate=rate).first()
            if existing_rate:
                return jsonify({'success': False, 'message': f'KM määr "{rate}%" on juba olemas'})
            
            # Auto-generate name based on rate
            name = f"{rate}%"
            
            # Create new VAT rate
            vat_rate = VatRate(
                name=name,
                rate=rate,
                description='',  # No descriptions in simplified approach
                is_active=is_active
            )
            
            db.session.add(vat_rate)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': 'KM määr lisatud',
                'vat_rate_id': vat_rate.id
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating VAT rate: {str(e)}")
            return jsonify({'success': False, 'message': 'Viga KM määra loomisel'})
    
    else:
        # Handle regular form request
        from app.forms import VatRateForm
        
        form = VatRateForm()
        
        if form.validate_on_submit():
            vat_rate = VatRate(
                name=form.name.data,
                rate=form.rate.data,
                description=form.description.data,
                is_active=form.is_active.data
            )
            
            try:
                db.session.add(vat_rate)
                db.session.commit()
                flash(f'KM määr "{vat_rate.name}" on edukalt loodud.', 'success')
                return redirect(url_for('dashboard.vat_rates'))
            except Exception as e:
                db.session.rollback()
                flash('KM määra loomisel tekkis viga. Palun proovi uuesti.', 'danger')
        
        return render_template('vat_rate_form.html', form=form, title='Uus KM määr')


@dashboard_bp.route('/settings/vat-rates/<int:vat_rate_id>/edit', methods=['GET', 'POST'])
def edit_vat_rate(vat_rate_id):
    """Edit VAT rate."""
    vat_rate = VatRate.query.get_or_404(vat_rate_id)
    
    if request.method == 'POST' and request.is_json:
        # Handle AJAX request from management modal
        data = request.get_json()
        
        try:
            # Validate input
            rate = float(data.get('rate', 0))
            is_active = data.get('is_active', True)
            
            if rate < 0 or rate > 100:
                return jsonify({'success': False, 'message': 'KM määr peab olema 0-100% vahel'})
            
            # Check for duplicates (excluding current record)
            existing_rate = VatRate.query.filter(VatRate.rate == rate, VatRate.id != vat_rate_id).first()
            if existing_rate:
                return jsonify({'success': False, 'message': f'KM määr "{rate}%" on juba olemas'})
            
            # Auto-generate name based on rate
            name = f"{rate}%"
            
            # Update VAT rate
            vat_rate.name = name
            vat_rate.rate = rate
            vat_rate.description = ''  # No descriptions in simplified approach
            vat_rate.is_active = is_active
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'KM määr uuendatud'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating VAT rate: {str(e)}")
            return jsonify({'success': False, 'message': 'Viga KM määra uuendamisel'})
    
    else:
        # Handle regular form request
        from app.forms import VatRateForm
        
        form = VatRateForm(obj=vat_rate)
        
        # Set VAT rate ID for unique validation
        form._vat_rate_id = vat_rate_id
        
        if form.validate_on_submit():
            vat_rate.name = form.name.data
            vat_rate.rate = form.rate.data
            vat_rate.description = form.description.data
            vat_rate.is_active = form.is_active.data
            
            try:
                db.session.commit()
                flash(f'KM määr "{vat_rate.name}" on edukalt uuendatud.', 'success')
                return redirect(url_for('dashboard.vat_rates'))
            except Exception as e:
                db.session.rollback()
                flash('KM määra uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
        
        return render_template('vat_rate_form.html', form=form, vat_rate=vat_rate, title='Muuda KM määra')


@dashboard_bp.route('/settings/vat-rates/<int:vat_rate_id>/delete', methods=['POST'])
def delete_vat_rate(vat_rate_id):
    """Delete VAT rate."""
    vat_rate = VatRate.query.get_or_404(vat_rate_id)
    
    if request.is_json:
        # Handle AJAX request from management modal
        try:
            # Check if VAT rate is used in any invoices
            invoice_count = Invoice.query.filter_by(vat_rate_id=vat_rate_id).count()
            if invoice_count > 0:
                return jsonify({
                    'success': False, 
                    'message': f'KM määra ei saa kustutada, kuna see on kasutusel {invoice_count} arvel'
                })
            
            vat_rate_name = vat_rate.name
            db.session.delete(vat_rate)
            db.session.commit()
            
            return jsonify({'success': True, 'message': f'KM määr "{vat_rate_name}" kustutatud'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting VAT rate: {str(e)}")
            return jsonify({'success': False, 'message': 'Viga KM määra kustutamisel'})
    
    else:
        # Handle regular form request
        # Check if VAT rate is used in any invoices
        invoice_count = Invoice.query.filter_by(vat_rate_id=vat_rate_id).count()
        if invoice_count > 0:
            flash(f'KM määra "{vat_rate.name}" ei saa kustutada, kuna see on kasutusel {invoice_count} arvel.', 'warning')
            return redirect(url_for('dashboard.vat_rates'))
        
        try:
            vat_rate_name = vat_rate.name
            db.session.delete(vat_rate)
            db.session.commit()
            flash(f'KM määr "{vat_rate_name}" on edukalt kustutatud.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('KM määra kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        
        return redirect(url_for('dashboard.vat_rates'))


@dashboard_bp.route('/settings/vat-rates/init-defaults', methods=['POST'])
def init_default_vat_rates():
    """Initialize default Estonian VAT rates."""
    try:
        VatRate.create_default_rates()
        flash('Vaikimisi KM määrad on edukalt loodud.', 'success')
    except Exception as e:
        flash('Vaikimisi KM määrade loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return redirect(url_for('dashboard.vat_rates'))


# Payment Terms Management Routes
@dashboard_bp.route('/settings/payment-terms', methods=['POST'])
def create_payment_term():
    """Create a new payment term."""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'days' not in data:
            return jsonify({'success': False, 'message': 'Puuduvad nõutavad andmed'})
        
        days = int(data['days'])
        is_default = data.get('is_default', False)
        is_active = data.get('is_active', True)
        
        if days < 0 or days > 365:
            return jsonify({'success': False, 'message': 'Päevade arv peab olema 0-365 vahel'})
        
        # Check for duplicates (only by days)
        existing_days = PaymentTerms.query.filter_by(days=days).first()
        if existing_days:
            return jsonify({'success': False, 'message': f'Päevade arv "{days}" on juba kasutusel'})
        
        # Auto-generate name based on days
        name = f"{days} {'päev' if days == 1 else 'päeva'}"
        
        # If setting as default, remove default from others
        if is_default:
            PaymentTerms.query.update({'is_default': False})
        
        # Create new payment term
        payment_term = PaymentTerms(
            name=name,
            days=days,
            is_default=is_default,
            is_active=is_active
        )
        
        db.session.add(payment_term)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Maksetingimus lisatud', 'payment_term_id': payment_term.id})
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Vigane päevade arv'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating payment term: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga maksetingimuse loomisel'})


@dashboard_bp.route('/settings/payment-terms/<int:term_id>', methods=['PUT'])
def update_payment_term(term_id):
    """Update a payment term."""
    try:
        payment_term = PaymentTerms.query.get_or_404(term_id)
        data = request.get_json()
        
        # Validate input
        if not data or 'days' not in data:
            return jsonify({'success': False, 'message': 'Puuduvad nõutavad andmed'})
        
        days = int(data['days'])
        is_default = data.get('is_default', False)
        is_active = data.get('is_active', True)
        
        if days < 0 or days > 365:
            return jsonify({'success': False, 'message': 'Päevade arv peab olema 0-365 vahel'})
        
        # Check for duplicates (excluding current record)
        existing_days = PaymentTerms.query.filter(
            PaymentTerms.days == days,
            PaymentTerms.id != term_id
        ).first()
        if existing_days:
            return jsonify({'success': False, 'message': f'Päevade arv "{days}" on juba kasutusel'})
        
        # Auto-generate name based on days
        name = f"{days} {'päev' if days == 1 else 'päeva'}"
        
        # If setting as default, remove default from others
        if is_default:
            PaymentTerms.query.filter(PaymentTerms.id != term_id).update({'is_default': False})
        
        # Update payment term
        payment_term.name = name
        payment_term.days = days
        payment_term.is_default = is_default
        payment_term.is_active = is_active
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Maksetingimus uuendatud'})
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Vigane päevade arv'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating payment term: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga maksetingimuse uuendamisel'})


@dashboard_bp.route('/settings/payment-terms/<int:term_id>', methods=['DELETE'])
def delete_payment_term(term_id):
    """Delete a payment term."""
    try:
        payment_term = PaymentTerms.query.get_or_404(term_id)
        
        # Don't allow deleting the default term
        if payment_term.is_default:
            return jsonify({'success': False, 'message': 'Vaikimisi maksetingimust ei saa kustutada'})
        
        # Check if payment term is used in any invoices
        invoice_count = Invoice.query.filter_by(payment_terms=payment_term.name).count()
        if invoice_count > 0:
            return jsonify({'success': False, 'message': f'Maksetingimust ei saa kustutada, kuna see on kasutusel {invoice_count} arvel'})
        
        term_name = payment_term.name
        db.session.delete(payment_term)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Maksetingimus "{term_name}" kustutatud'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting payment term: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga maksetingimuse kustutamisel'})


@dashboard_bp.route('/settings/payment-terms/init-defaults', methods=['POST'])
def init_default_payment_terms():
    """Initialize default payment terms."""
    try:
        PaymentTerms.create_default_terms()
        flash('Vaikimisi maksetingimused on edukalt loodud.', 'success')
    except Exception as e:
        logger.error(f"Error creating default payment terms: {str(e)}")
        flash('Vaikimisi maksetingimuste loomisel tekkis viga.', 'danger')
    
    return redirect(url_for('dashboard.settings'))


@dashboard_bp.route('/settings/vat-rates-list')
def get_vat_rates_list():
    """Get VAT rates list for management modal."""
    vat_rates = VatRate.query.order_by(VatRate.rate.asc()).all()
    
    rates_data = []
    for rate in vat_rates:
        rates_data.append({
            'id': rate.id,
            'name': rate.name,
            'rate': float(rate.rate),
            'description': rate.description or '',
            'is_active': rate.is_active
        })
    
    return jsonify({'vat_rates': rates_data})


@dashboard_bp.route('/settings/payment-terms-list')
def get_payment_terms_list():
    """Get payment terms list for management modal."""
    try:
        payment_terms = PaymentTerms.query.order_by(PaymentTerms.days.asc()).all()
        
        terms_data = []
        for term in payment_terms:
            terms_data.append({
                'id': term.id,
                'name': term.name,
                'days': term.days,
                'is_default': term.is_default,
                'is_active': term.is_active
            })
        
        return jsonify({'payment_terms': terms_data})
    except:
        return jsonify({'payment_terms': []})


# PDF Templates Management Routes
@dashboard_bp.route('/settings/pdf-templates')
def pdf_templates():
    """PDF templates management page."""
    import os
    
    # Define available templates
    templates = [
        {
            'id': 'standard',
            'name': 'Standard',
            'description': 'Klassikaline ärilik disain',
            'file': 'templates/pdf/invoice_standard.html'
        },
        {
            'id': 'modern', 
            'name': 'Modern',
            'description': 'Kaasaegne disain gradientidega',
            'file': 'templates/pdf/invoice_modern.html'
        },
        {
            'id': 'elegant',
            'name': 'Elegant', 
            'description': 'Elegantne disain seriifkirjaga',
            'file': 'templates/pdf/invoice_elegant.html'
        },
        {
            'id': 'minimal',
            'name': 'Minimal',
            'description': 'Minimaalne puhas disain',
            'file': 'templates/pdf/invoice_minimal.html'
        },
        {
            'id': 'classic',
            'name': 'Classic',
            'description': 'Klassikaline traditsiooniliine disain',
            'file': 'templates/pdf/invoice_classic.html'
        }
    ]
    
    # Check which templates exist
    for template in templates:
        template_path = os.path.join(os.getcwd(), template['file'])
        template['exists'] = os.path.exists(template_path)
        template['size'] = os.path.getsize(template_path) if template['exists'] else 0
    
    # Get company settings for default template and logos
    from app.models import CompanySettings
    company_settings = CompanySettings.get_settings()
    default_template = company_settings.default_pdf_template
    
    # Add logo information to each template
    template_logos = company_settings.get_all_template_logos()
    for template in templates:
        template['logo_url'] = template_logos.get(template['id'], '')
        template['has_logo'] = bool(template['logo_url'])
        template['fallback_logo'] = company_settings.company_logo_url
    
    return render_template('pdf_templates.html', 
                         templates=templates,
                         default_template=default_template,
                         company_settings=company_settings)


@dashboard_bp.route('/settings/pdf-templates/<template_id>/upload-logo', methods=['POST'])
def upload_template_logo(template_id):
    """Handle template-specific logo file upload."""
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        return jsonify({'success': False, 'message': 'Vigane mall'}), 400
    
    if 'logo' not in request.files:
        return jsonify({'success': False, 'message': 'Fail puudub'}), 400
    
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Fail ei ole valitud'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'svg', 'gif'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'success': False, 'message': 'Lubatud failiformaadid: PNG, JPG, JPEG, SVG, GIF'}), 400
    
    # Validate file size (2MB max)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 2 * 1024 * 1024:  # 2MB
        return jsonify({'success': False, 'message': 'Faili suurus on liiga suur (max 2MB)'}), 400
    
    try:
        # Generate unique filename with template prefix
        filename = secure_filename(file.filename)
        unique_filename = f"{template_id}_{uuid.uuid4().hex}_{filename}"
        
        # Ensure uploads directory exists
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        filepath = os.path.join(upload_dir, unique_filename)
        file.save(filepath)
        
        # Update company settings with template-specific logo
        from app.models import CompanySettings
        company_settings = CompanySettings.get_settings()
        logo_url = f"/static/uploads/{unique_filename}"
        
        if company_settings.set_logo_for_template(template_id, logo_url):
            return jsonify({
                'success': True, 
                'message': f'{template_id.capitalize()} malli logo edukalt üles laaditud',
                'url': logo_url,
                'template_id': template_id
            })
        else:
            return jsonify({'success': False, 'message': 'Viga logo salvestamisel'}), 500
        
    except Exception as e:
        logger.error(f"Error uploading template logo: {str(e)}")
        return jsonify({'success': False, 'message': 'Faili üleslaadimisel tekkis viga'}), 500


@dashboard_bp.route('/settings/pdf-templates/<template_id>/remove-logo', methods=['POST'])
def remove_template_logo(template_id):
    """Remove template-specific logo."""
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        return jsonify({'success': False, 'message': 'Vigane mall'}), 400
    
    try:
        from app.models import CompanySettings
        company_settings = CompanySettings.get_settings()
        
        if company_settings.set_logo_for_template(template_id, ''):
            return jsonify({
                'success': True, 
                'message': f'{template_id.capitalize()} malli logo eemaldatud',
                'template_id': template_id
            })
        else:
            return jsonify({'success': False, 'message': 'Viga logo eemaldamisel'}), 500
            
    except Exception as e:
        logger.error(f"Error removing template logo: {str(e)}")
        return jsonify({'success': False, 'message': 'Logo eemaldamisel tekkis viga'}), 500


@dashboard_bp.route('/settings/pdf-templates/<template_id>')
def view_pdf_template(template_id):
    """View/edit a specific PDF template (code editor)."""
    import os
    
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        flash('Vigane mall.', 'error')
        return redirect(url_for('dashboard.pdf_templates'))
    
    # Read template file
    template_file = f'templates/pdf/invoice_{template_id}.html'
    template_path = os.path.join(os.getcwd(), template_file)
    
    if not os.path.exists(template_path):
        flash('Mall ei leitud.', 'error')
        return redirect(url_for('dashboard.pdf_templates'))
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        logger.error(f"Error reading template {template_id}: {str(e)}")
        flash('Malli lugemise viga.', 'error')
        return redirect(url_for('dashboard.pdf_templates'))
    
    template_info = {
        'id': template_id,
        'name': template_id.capitalize(),
        'description': {
            'standard': 'Klassikaline ärilik disain',
            'modern': 'Kaasaegne disain gradientidega', 
            'elegant': 'Elegantne disain seriifkirjaga',
            'minimal': 'Minimaalne puhas disain'
        }.get(template_id, ''),
        'content': template_content
    }
    
    return render_template('pdf_template_editor.html', template=template_info)


@dashboard_bp.route('/settings/pdf-templates/<template_id>/visual')
def visual_pdf_template(template_id):
    """Visual drag & drop PDF template editor."""
    import os
    
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        flash('Vigane mall.', 'error')
        return redirect(url_for('dashboard.pdf_templates'))
    
    # Get template metadata
    template_info = {
        'id': template_id,
        'name': template_id.capitalize(),
        'description': {
            'standard': 'Klassikaline ärilik disain',
            'modern': 'Kaasaegne disain gradientidega', 
            'elegant': 'Elegantne disain seriifkirjaga',
            'minimal': 'Minimaalne puhas disain'
        }.get(template_id, ''),
    }
    
    # Get sample invoice data for preview
    from app.models import Invoice, Client, CompanySettings
    sample_invoice = None
    sample_client = None
    
    # Try to get a real invoice for preview, otherwise create sample data
    try:
        sample_invoice = Invoice.query.first()
        if sample_invoice:
            sample_client = sample_invoice.client
    except:
        pass
    
    # Create sample data (always use sample to avoid template issues)
    from datetime import date, timedelta
    
    # Use real data if available, otherwise fallback to sample
    if sample_invoice and sample_client:
        sample_client_data = {
            'name': sample_client.name or 'Näidisklient OÜ',
            'email': sample_client.email or 'klient@naidisettvotte.ee',
            'phone': sample_client.phone or '+372 123 4567',
            'address': sample_client.address or 'Tallinn, Eesti',
            'registry_code': sample_client.registry_code or '12345678'
        }
        
        sample_invoice_data = {
            'number': sample_invoice.number or 'INV-2025-001',
            'date': sample_invoice.date or date.today(),
            'due_date': sample_invoice.due_date or (date.today() + timedelta(days=14)),
            'subtotal': float(sample_invoice.subtotal) if sample_invoice.subtotal else 100.00,
            'total': float(sample_invoice.total) if sample_invoice.total else 124.00,
            'vat_amount': float(sample_invoice.vat_amount) if sample_invoice.vat_amount else 24.00,
            'status': sample_invoice.status or 'maksmata',
            'note': sample_invoice.note or 'Näidis märkus',
            'announcements': sample_invoice.announcements or 'Info ja teadaanded'
        }
        
        sample_lines = []
        if sample_invoice.lines:
            for line in sample_invoice.lines:
                sample_lines.append({
                    'description': line.description or 'Teenus',
                    'qty': float(line.qty) if line.qty else 1.0,
                    'unit_price': float(line.unit_price) if line.unit_price else 0.0,
                    'line_total': float(line.line_total) if line.line_total else 0.0
                })
        else:
            sample_lines = [
                {'description': 'Teenus 1', 'qty': 2, 'unit_price': 30.00, 'line_total': 60.00},
                {'description': 'Teenus 2', 'qty': 1, 'unit_price': 40.00, 'line_total': 40.00}
            ]
    else:
        # Default sample data when no real data is available
        sample_client_data = {
            'name': 'Näidisklient OÜ',
            'email': 'klient@naidisettvotte.ee',
            'phone': '+372 123 4567',
            'address': 'Tallinn, Eesti',
            'registry_code': '12345678'
        }
        
        sample_invoice_data = {
            'number': 'INV-2025-001',
            'date': date.today(),
            'due_date': date.today() + timedelta(days=14),
            'subtotal': 100.00,
            'total': 124.00,
            'vat_amount': 24.00,
            'status': 'maksmata',
            'note': 'Näidis märkus',
            'announcements': 'Info ja teadaanded'
        }
        
        sample_lines = [
            {'description': 'Teenus 1', 'qty': 2, 'unit_price': 30.00, 'line_total': 60.00},
            {'description': 'Teenus 2', 'qty': 1, 'unit_price': 40.00, 'line_total': 40.00}
        ]
    
    # Get company settings
    company_settings = CompanySettings.get_settings()
    
    return render_template('visual_pdf_editor.html', 
                         template=template_info,
                         sample_client=sample_client_data,
                         sample_invoice=sample_invoice_data,
                         sample_lines=sample_lines,
                         company=company_settings)


@dashboard_bp.route('/settings/pdf-templates/<template_id>/save', methods=['POST'])
def save_pdf_template(template_id):
    """Save PDF template changes."""
    import os
    
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        return jsonify({'success': False, 'message': 'Vigane mall'})
    
    # Get template content from request
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'success': False, 'message': 'Puudub malli sisu'})
    
    template_content = data['content']
    
    # Validate HTML (basic check)
    if '<html>' not in template_content or '<body>' not in template_content:
        return jsonify({'success': False, 'message': 'Vigane HTML struktuur'})
    
    # Create backup before saving
    template_file = f'templates/pdf/invoice_{template_id}.html'
    template_path = os.path.join(os.getcwd(), template_file)
    backup_path = f'{template_path}.backup'
    
    try:
        # Create backup
        if os.path.exists(template_path):
            import shutil
            shutil.copy2(template_path, backup_path)
        
        # Save new content
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        return jsonify({'success': True, 'message': 'Mall salvestatud'})
        
    except Exception as e:
        logger.error(f"Error saving template {template_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Malli salvestamise viga'})


@dashboard_bp.route('/settings/pdf-templates/<template_id>/reset', methods=['POST'])
def reset_pdf_template(template_id):
    """Reset PDF template to backup."""
    import os
    
    # Validate template ID
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template_id not in valid_templates:
        return jsonify({'success': False, 'message': 'Vigane mall'})
    
    template_file = f'templates/pdf/invoice_{template_id}.html'
    template_path = os.path.join(os.getcwd(), template_file)
    backup_path = f'{template_path}.backup'
    
    try:
        if os.path.exists(backup_path):
            import shutil
            shutil.copy2(backup_path, template_path)
            return jsonify({'success': True, 'message': 'Mall taastatud'})
        else:
            return jsonify({'success': False, 'message': 'Varundus puudub'})
            
    except Exception as e:
        logger.error(f"Error resetting template {template_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Malli taastamise viga'})


# Penalty Rates Management Routes
@dashboard_bp.route('/settings/penalty-rates', methods=['POST'])
def create_penalty_rate():
    """Create a new penalty rate."""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'rate_per_day' not in data:
            return jsonify({'success': False, 'message': 'Puuduvad nõutavad andmed'})
        
        rate_per_day = float(data['rate_per_day'])
        is_default = data.get('is_default', False)
        is_active = data.get('is_active', True)
        
        if rate_per_day < 0 or rate_per_day > 10:
            return jsonify({'success': False, 'message': 'Viivise määr peab olema 0-10% vahel'})
        
        # Check for duplicates (only by rate_per_day)
        existing_rate = PenaltyRate.query.filter_by(rate_per_day=rate_per_day).first()
        if existing_rate:
            return jsonify({'success': False, 'message': f'Viivise määr "{rate_per_day}%" on juba kasutusel'})
        
        # Auto-generate name based on rate
        if rate_per_day == 0:
            name = "0% päevas"
        elif rate_per_day == int(rate_per_day):
            name = f"{int(rate_per_day)}% päevas"
        else:
            name = f"{rate_per_day:.1f}% päevas".replace('.', ',')
        
        # If setting as default, remove default from others
        if is_default:
            PenaltyRate.query.update({'is_default': False})
        
        # Create new penalty rate
        penalty_rate = PenaltyRate(
            name=name,
            rate_per_day=rate_per_day,
            is_default=is_default,
            is_active=is_active
        )
        
        db.session.add(penalty_rate)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Viivis lisatud', 'penalty_rate_id': penalty_rate.id})
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Vigane viivise määr'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating penalty rate: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga viivise loomisel'})


@dashboard_bp.route('/settings/penalty-rates/<int:rate_id>', methods=['PUT'])
def update_penalty_rate(rate_id):
    """Update a penalty rate."""
    try:
        penalty_rate = PenaltyRate.query.get_or_404(rate_id)
        data = request.get_json()
        
        # Validate input
        if not data or 'rate_per_day' not in data:
            return jsonify({'success': False, 'message': 'Puuduvad nõutavad andmed'})
        
        rate_per_day = float(data['rate_per_day'])
        is_default = data.get('is_default', False)
        is_active = data.get('is_active', True)
        
        if rate_per_day < 0 or rate_per_day > 10:
            return jsonify({'success': False, 'message': 'Viivise määr peab olema 0-10% vahel'})
        
        # Check for duplicates (excluding current record)
        existing_rate = PenaltyRate.query.filter(
            PenaltyRate.rate_per_day == rate_per_day,
            PenaltyRate.id != rate_id
        ).first()
        if existing_rate:
            return jsonify({'success': False, 'message': f'Viivise määr "{rate_per_day}%" on juba kasutusel'})
        
        # Auto-generate name based on rate
        if rate_per_day == 0:
            name = "0% päevas"
        elif rate_per_day == int(rate_per_day):
            name = f"{int(rate_per_day)}% päevas"
        else:
            name = f"{rate_per_day:.1f}% päevas".replace('.', ',')
        
        # If setting as default, remove default from others
        if is_default:
            PenaltyRate.query.filter(PenaltyRate.id != rate_id).update({'is_default': False})
        
        # Update penalty rate
        penalty_rate.name = name
        penalty_rate.rate_per_day = rate_per_day
        penalty_rate.is_default = is_default
        penalty_rate.is_active = is_active
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Viivis uuendatud'})
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Vigane viivise määr'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating penalty rate: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga viivise uuendamisel'})


@dashboard_bp.route('/settings/penalty-rates/<int:rate_id>', methods=['DELETE'])
def delete_penalty_rate(rate_id):
    """Delete a penalty rate."""
    try:
        penalty_rate = PenaltyRate.query.get_or_404(rate_id)
        
        # Don't allow deleting the default rate
        if penalty_rate.is_default:
            return jsonify({'success': False, 'message': 'Vaikimisi viiviset ei saa kustutada'})
        
        rate_name = penalty_rate.name
        db.session.delete(penalty_rate)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Viivis "{rate_name}" kustutatud'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting penalty rate: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga viivise kustutamisel'})


@dashboard_bp.route('/settings/penalty-rates/init-defaults', methods=['POST'])
def init_default_penalty_rates():
    """Initialize default penalty rates."""
    try:
        PenaltyRate.create_default_rates()
        flash('Vaikimisi viivised on edukalt loodud.', 'success')
    except Exception as e:
        logger.error(f"Error creating default penalty rates: {str(e)}")
        flash('Vaikimisi viiviste loomisel tekkis viga.', 'danger')
    
    return redirect(url_for('dashboard.settings'))


@dashboard_bp.route('/settings/penalty-rates-list')
def get_penalty_rates_list():
    """Get penalty rates list for management modal."""
    try:
        penalty_rates = PenaltyRate.query.order_by(PenaltyRate.rate_per_day.asc()).all()
        
        rates_data = []
        for rate in penalty_rates:
            rates_data.append({
                'id': rate.id,
                'name': rate.name,
                'rate_per_day': float(rate.rate_per_day),
                'is_default': rate.is_default,
                'is_active': rate.is_active
            })
        
        return jsonify({'penalty_rates': rates_data})
    except:
        return jsonify({'penalty_rates': []})


# Note Labels Management Routes
@dashboard_bp.route('/settings/note-labels', methods=['POST'])
def create_note_label():
    """Create a new note label."""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'name' not in data:
            return jsonify({'success': False, 'message': 'Puuduvad nõutavad andmed'})
        
        name = data['name'].strip()
        is_default = data.get('is_default', False)
        
        if not name:
            return jsonify({'success': False, 'message': 'Märkuse sildi nimi on kohustuslik'})
        
        if len(name) > 50:
            return jsonify({'success': False, 'message': 'Märkuse sildi nimi peab olema kuni 50 tähemärki'})
        
        # Check for duplicates
        existing_label = NoteLabel.query.filter_by(name=name).first()
        if existing_label:
            return jsonify({'success': False, 'message': f'Märkuse silt "{name}" on juba olemas'})
        
        # If setting as default, check if there's already a default
        if is_default:
            existing_default = NoteLabel.query.filter_by(is_default=True).first()
            if existing_default:
                # Remove default from existing
                existing_default.is_default = False
        
        # Create the note label
        new_label = NoteLabel(
            name=name,
            is_default=is_default,
            is_active=True
        )
        
        db.session.add(new_label)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Märkuse silt "{name}" lisatud'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating note label: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga märkuse sildi loomisel'})


@dashboard_bp.route('/settings/note-labels/<int:label_id>', methods=['DELETE'])
def delete_note_label(label_id):
    """Delete a note label."""
    try:
        note_label = NoteLabel.query.get_or_404(label_id)
        
        # Don't allow deleting the default label if it's the only one
        if note_label.is_default:
            other_labels = NoteLabel.query.filter(NoteLabel.id != label_id).count()
            if other_labels == 0:
                return jsonify({'success': False, 'message': 'Viimast märkuse silti ei saa kustutada'})
            
            # Set another label as default
            first_other = NoteLabel.query.filter(NoteLabel.id != label_id).first()
            if first_other:
                first_other.is_default = True
        
        label_name = note_label.name
        db.session.delete(note_label)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Märkuse silt "{label_name}" kustutatud'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting note label: {str(e)}")
        return jsonify({'success': False, 'message': 'Viga märkuse sildi kustutamisel'})


@dashboard_bp.route('/settings/note-labels-list')
def get_note_labels_list():
    """Get note labels list for management modal."""
    try:
        note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
        
        labels_data = []
        for label in note_labels:
            labels_data.append({
                'id': label.id,
                'name': label.name,
                'is_default': label.is_default,
                'is_active': label.is_active
            })
        
        return jsonify({'note_labels': labels_data})
    except:
        return jsonify({'note_labels': []})