from flask import Blueprint, render_template, request, send_file, abort
from datetime import date
from io import BytesIO
from weasyprint import HTML, CSS
from app.models import Invoice, CompanySettings, NoteLabel, db
from app.logging_config import get_logger

logger = get_logger(__name__)

pdf_bp = Blueprint('pdf', __name__)


@pdf_bp.route('/invoice/<int:id>/pdf')
@pdf_bp.route('/invoice/<int:id>/pdf/<template>')
def invoice_pdf(id, template=None):
    """Generate PDF for invoice with specified template."""
    invoice = Invoice.query.get_or_404(id)
    
    # Get company settings for default template
    company_settings = CompanySettings.get_settings()
    
    # Determine template to use (priority: URL param > query param > invoice preference > settings default)
    if not template:
        # Support both ?template= and ?style= parameters for backwards compatibility
        if 'style' in request.args:
            template = request.args.get('style')
        elif 'template' in request.args:
            template = request.args.get('template')
        else:
            # Use invoice preference or fallback to settings default
            template = invoice.get_preferred_pdf_template()
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template not in valid_templates:
        template = company_settings.default_pdf_template or 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Convert relative logo URL to absolute for WeasyPrint
        company_logo_absolute = None
        if company_settings.company_logo_url:
            if company_settings.company_logo_url.startswith('http'):
                # Already absolute URL
                company_logo_absolute = company_settings.company_logo_url
            elif company_settings.company_logo_url.startswith('/static/'):
                # Convert relative static URL to absolute file path
                import os
                from flask import current_app
                
                # Get the static folder path
                static_folder = current_app.static_folder
                # Remove /static/ prefix and create absolute path
                logo_path = company_settings.company_logo_url[8:]  # Remove '/static/'
                absolute_logo_path = os.path.join(static_folder, logo_path)
                
                # Check if file exists
                if os.path.exists(absolute_logo_path):
                    company_logo_absolute = f"file://{absolute_logo_path}"
                    logger.info(f"Converting logo path for PDF: {company_settings.company_logo_url} -> {company_logo_absolute}")
        
        # Get note label for the invoice
        try:
            logger.debug(f"PDF route - Invoice {invoice.id} note_label_id: {invoice.note_label_id}")
            if invoice.note_label_id:
                # Get the note label directly
                note_label_obj = db.session.get(NoteLabel, invoice.note_label_id)
                if note_label_obj:
                    note_label_text = note_label_obj.name
                    logger.debug(f"PDF route - Using invoice-specific note label: {note_label_text}")
                else:
                    # Fallback if note label not found
                    note_label_text = "Märkus"
                    logger.debug(f"PDF route - Note label not found, using fallback")
            else:
                # No note label assigned to invoice
                note_label_text = None
                logger.debug(f"PDF route - No note label assigned to invoice")
        except Exception as e:
            logger.error(f"PDF route - Error getting note label: {e}")
            note_label_text = None
        
        # Render HTML with invoice data and company settings
        html = render_template(
            template_file, 
            invoice=invoice, 
            company=company_settings,
            company_logo_absolute=company_logo_absolute,
            note_label=note_label_text,
            today=date.today()
        )
        
        # Generate PDF with WeasyPrint
        html_doc = HTML(string=html)
        pdf_bytes = html_doc.write_pdf()
        
        # Create filename with client name
        client_name_safe = "".join(c for c in invoice.client.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        client_name_safe = client_name_safe.replace(' ', '_')
        filename = f"{invoice.number}_{client_name_safe}.pdf"
        
        pdf_buffer = BytesIO(pdf_bytes)
        return send_file(
            pdf_buffer, 
            mimetype='application/pdf', 
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"PDF generation error for invoice {id}: {str(e)}", exc_info=True)
        abort(500)


@pdf_bp.route('/invoice/<int:id>/preview')
@pdf_bp.route('/invoice/<int:id>/preview/<template>')
def invoice_preview(id, template=None):
    """Preview invoice HTML before PDF generation."""
    invoice = Invoice.query.get_or_404(id)
    
    # Get company settings for default template
    company_settings = CompanySettings.get_settings()
    
    # Determine template to use (priority: URL param > query param > invoice preference > settings default)
    if not template:
        template = request.args.get('template') or request.args.get('style') or invoice.get_preferred_pdf_template()
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant', 'minimal', 'classic']
    if template not in valid_templates:
        template = company_settings.default_pdf_template or 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Get note label for the invoice (same logic as PDF route)
        try:
            logger.debug(f"Preview route - Invoice {invoice.id} note_label_id: {invoice.note_label_id}")
            if invoice.note_label_id:
                # Get the note label directly
                note_label_obj = db.session.get(NoteLabel, invoice.note_label_id)
                if note_label_obj:
                    note_label_text = note_label_obj.name
                    logger.debug(f"Preview route - Using invoice-specific note label: {note_label_text}")
                else:
                    # Fallback if note label not found
                    note_label_text = "Märkus"
                    logger.debug(f"Preview route - Note label not found, using fallback")
            else:
                # No note label assigned to invoice
                note_label_text = None
                logger.debug(f"Preview route - No note label assigned to invoice")
        except Exception as e:
            logger.error(f"Preview route - Error getting note label: {e}")
            note_label_text = None
        
        # Render and return HTML directly with company settings
        return render_template(
            template_file, 
            invoice=invoice, 
            company=company_settings,
            note_label=note_label_text,
            today=date.today()
        )
    except Exception as e:
        logger.error(f"Preview generation error for invoice {id}: {str(e)}", exc_info=True)
        abort(500)


@pdf_bp.route('/invoice/<int:id>/pdf/all')
def invoice_pdf_all_templates(id):
    """Generate PDFs in all templates and return as zip file (future enhancement)."""
    # This could be implemented to generate all three templates
    # and return them as a zip file for comparison
    invoice = Invoice.query.get_or_404(id)
    
    # For now, redirect to standard template
    return invoice_pdf(id, 'standard')