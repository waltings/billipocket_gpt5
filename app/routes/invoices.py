from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import db, Invoice, Client, InvoiceLine, VatRate, CompanySettings, PaymentTerms, NoteLabel
from app.forms import InvoiceForm, InvoiceSearchForm, InvoiceLineForm
from app.services.numbering import generate_invoice_number
from app.services.totals import calculate_invoice_totals, calculate_line_total
from app.services.status_transitions import InvoiceStatusTransition
from app.logging_config import get_logger
from datetime import date, datetime
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

logger = get_logger(__name__)

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('/invoices')
def invoices():
    """Invoices management page with filtering."""
    search_form = InvoiceSearchForm()
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    search_form.client_id.choices = [('', 'Kõik kliendid')] + [(str(c.id), c.name) for c in clients]
    
    # Get filter parameters
    status = request.args.get('status', '').strip()
    client_id = request.args.get('client_id', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'date').strip()
    sort_dir = request.args.get('dir', 'desc').strip()
    try:
        per_page = int(request.args.get('per_page', 10))
        # Limit per_page to reasonable values
        per_page = max(1, min(per_page, 1000))
    except (ValueError, TypeError):
        per_page = 10
        
    try:
        page = int(request.args.get('page', 1))
        page = max(1, page)  # Ensure page is at least 1
    except (ValueError, TypeError):
        page = 1
    
    # Update overdue status before querying
    updated_count = Invoice.update_overdue_invoices()
    if updated_count > 0:
        db.session.commit()
    
    # Build query
    query = Invoice.query.join(Client)
    
    if status and status != '':
        if status == 'overdue':
            # Special case for overdue invoices - get unpaid invoices that are overdue
            query = query.filter(Invoice.status == 'maksmata')
            # Filter for overdue will be applied after the query since it's a property
            # We'll handle this in the final filtering step
        else:
            query = query.filter(Invoice.status == status)
    
    if client_id and client_id != '':
        query = query.filter(Invoice.client_id == int(client_id))
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Search functionality
    if search_query:
        search_filter = or_(
            Invoice.number.ilike(f'%{search_query}%'),
            Client.name.ilike(f'%{search_query}%')
        )
        query = query.filter(search_filter)
    
    # Sorting
    if sort_by == 'number':
        if sort_dir == 'asc':
            query = query.order_by(Invoice.number.asc())
        else:
            query = query.order_by(Invoice.number.desc())
    elif sort_by == 'client':
        if sort_dir == 'asc':
            query = query.order_by(Client.name.asc())
        else:
            query = query.order_by(Client.name.desc())
    elif sort_by == 'due_date':
        if sort_dir == 'asc':
            query = query.order_by(Invoice.due_date.asc())
        else:
            query = query.order_by(Invoice.due_date.desc())
    elif sort_by == 'total':
        if sort_dir == 'asc':
            query = query.order_by(Invoice.total.asc())
        else:
            query = query.order_by(Invoice.total.desc())
    elif sort_by == 'status':
        if sort_dir == 'asc':
            query = query.order_by(Invoice.status.asc())
        else:
            query = query.order_by(Invoice.status.desc())
    else:  # date
        if sort_dir == 'asc':
            query = query.order_by(Invoice.date.asc())
        else:
            query = query.order_by(Invoice.date.desc())
    
    # Get total count before pagination for statistics
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    invoices_list = query.offset(offset).limit(per_page).all()
    
    # Special handling for overdue filter
    if status == 'overdue':
        # For overdue, we need to filter after getting all records since it's a computed property
        all_unpaid = query.all()
        overdue_invoices = [invoice for invoice in all_unpaid if invoice.is_overdue]
        total_count = len(overdue_invoices)
        
        # Apply pagination to overdue results
        invoices_list = overdue_invoices[offset:offset + per_page]
    
    # Calculate statistics for filter buttons
    all_invoices = Invoice.query.all()
    status_counts = {
        'all': len(all_invoices),
        'makstud': len([i for i in all_invoices if i.status == 'makstud']),
        'maksmata': len([i for i in all_invoices if i.status == 'maksmata']),
        'overdue': len([i for i in all_invoices if i.is_overdue and i.status == 'maksmata'])
    }
    
    # Prepare invoice data
    invoices_data = []
    for invoice in invoices_list:
        invoices_data.append({
            'id': invoice.id,
            'no': invoice.number,
            'date': invoice.date.strftime('%d.%m.%Y'),
            'due_date': invoice.due_date.strftime('%d.%m.%Y'),
            'client': invoice.client.name,
            'client_id': invoice.client_id,
            'total': float(invoice.total),
            'status': invoice.status,
            'status_display': invoice.status_display,
            'status_color': invoice.status_color,
            'is_overdue': invoice.is_overdue
        })
    
    # Set form data
    search_form.status.data = status
    search_form.client_id.data = client_id
    search_form.search.data = search_query
    if date_from:
        try:
            search_form.date_from.data = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    if date_to:
        try:
            search_form.date_to.data = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Get company settings for default PDF template
    from app.models import CompanySettings
    company_settings = CompanySettings.get_settings()
    
    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page
    start_item = offset + 1 if invoices_list else 0
    end_item = min(offset + per_page, total_count)
    
    return render_template('invoices.html', 
                         invoices=invoices_data, 
                         search_form=search_form,
                         default_pdf_template=company_settings.default_pdf_template,
                         status_counts=status_counts,
                         current_status=status,
                         current_search=search_query,
                         current_sort=sort_by,
                         current_dir=sort_dir,
                         current_client_id=client_id,
                         clients=clients,
                         # Pagination data
                         current_page=page,
                         per_page=per_page,
                         total_count=total_count,
                         total_pages=total_pages,
                         start_item=start_item,
                         end_item=end_item)


@invoices_bp.route('/invoices/new', methods=['GET', 'POST'])
def new_invoice():
    """Create new invoice."""
    form = InvoiceForm()
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    form.client_id.choices = [(c.id, c.name) for c in clients]
    
    if not clients:
        flash('Enne arve loomist tuleb lisada vähemalt üks klient.', 'warning')
        return redirect(url_for('clients.new_client'))
    
    # Populate payment terms choices
    try:
        payment_terms_choices = [('', 'Vali makse tingimus...')] + PaymentTerms.get_choices()
    except:
        # Fallback to static choices if PaymentTerms table doesn't exist yet
        payment_terms_choices = [('', 'Vali makse tingimus...'), ('14 päeva', '14 päeva')]
    
    form.payment_terms.choices = payment_terms_choices
    
    # Get company settings for defaults
    company_settings = CompanySettings.get_settings()
    
    # Populate VAT rate choices and set default
    vat_rates = VatRate.get_active_rates()
    
    # Set default VAT rate from company settings
    if not form.vat_rate_id.data:
        # Try to get default from company settings
        default_vat_rate = company_settings.default_vat_rate_obj
        if default_vat_rate:
            form.vat_rate_id.data = default_vat_rate.id
        else:
            # Fallback to standard Estonian rate or first available
            standard_rate = VatRate.get_default_rate()
            if standard_rate:
                form.vat_rate_id.data = standard_rate.id
            elif vat_rates:
                form.vat_rate_id.data = vat_rates[0].id
    
    # Set default payment terms from company settings
    if not form.payment_terms.data:
        try:
            # First try to get from company settings
            if company_settings.default_payment_terms_obj:
                form.payment_terms.data = company_settings.default_payment_terms_obj.name
            else:
                # Fall back to default payment term
                default_payment_term = PaymentTerms.get_default_term()
                if default_payment_term:
                    form.payment_terms.data = default_payment_term.name
        except:
            pass  # Leave empty if no default available
    
    # Auto-populate invoice number if not set
    if not form.number.data:
        form.number.data = generate_invoice_number()
    
    # Pre-select client if client_id is provided in URL
    client_id = request.args.get('client_id')
    if client_id and not form.client_id.data:
        try:
            form.client_id.data = int(client_id)
        except (ValueError, TypeError):
            pass
    
    
    
    if form.validate_on_submit():
        # Debug all form data
        logger.debug(f"Form validated - all form data: {dict(request.form)}")
        logger.debug(f"Form vat_rate_id.data: '{form.vat_rate_id.data}'")
        
        # Custom validation: check if form is valid and has at least one complete line
        valid_lines = []
        for line_form in form.lines.entries:
            # Check description
            has_description = (hasattr(line_form, 'description') and 
                             hasattr(line_form.description, 'data') and
                             line_form.description.data and 
                             line_form.description.data.strip())
            
            # Check qty
            has_qty = (hasattr(line_form, 'qty') and 
                      hasattr(line_form.qty, 'data') and
                      line_form.qty.data is not None)
            
            # Check unit_price
            has_unit_price = (hasattr(line_form, 'unit_price') and 
                             hasattr(line_form.unit_price, 'data') and
                             line_form.unit_price.data is not None)
            
            if has_description and has_qty and has_unit_price:
                valid_lines.append(line_form)
        
        if len(valid_lines) == 0:
            # Try accessing data via the .data attribute instead
            for line_form in form.lines.entries:
                try:
                    data = line_form.data
                    desc = data.get('description', '').strip() if data else ''
                    qty = data.get('qty') if data else None
                    price = data.get('unit_price') if data else None
                    
                    if desc and qty is not None and price is not None:
                        valid_lines.append(line_form)
                except Exception as e:
                    logger.error(f"Error accessing line_form data: {e}")
            
            if len(valid_lines) == 0:
                flash('Palun lisa vähemalt üks arve rida.', 'warning')
        
        if len(valid_lines) > 0:
            # Use form invoice number (user can modify it)
            invoice_number = form.number.data or generate_invoice_number()
        
            # Create invoice
            # Get the selected VAT rate (convert string to int) - with proper validation
            logger.debug(f"Form VAT rate ID data: '{form.vat_rate_id.data}' (type: {type(form.vat_rate_id.data)})")
            logger.debug(f"Raw form data vat_rate_id: '{request.form.get('vat_rate_id')}'")
            
            try:
                # Try to get from form first, then fallback to raw form data
                vat_rate_id_raw = form.vat_rate_id.data or request.form.get('vat_rate_id')
                vat_rate_id = int(vat_rate_id_raw) if vat_rate_id_raw else None
                logger.debug(f"Creating invoice with VAT rate ID: {vat_rate_id_raw} -> {vat_rate_id}")
                selected_vat_rate = VatRate.query.get(vat_rate_id) if vat_rate_id is not None else None
                
                if vat_rate_id is not None and not selected_vat_rate:
                    logger.warning(f"VAT rate with ID {vat_rate_id} not found, using default")
                    # Fallback to default VAT rate
                    selected_vat_rate = VatRate.get_default_rate()
                    vat_rate_id = selected_vat_rate.id if selected_vat_rate else None
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid VAT rate ID: {form.vat_rate_id.data}, using default. Error: {e}")
                selected_vat_rate = VatRate.get_default_rate()
                vat_rate_id = selected_vat_rate.id if selected_vat_rate else None
            
            invoice = Invoice(
                number=invoice_number,
                client_id=form.client_id.data,
                date=form.date.data,
                due_date=form.due_date.data,
                vat_rate_id=vat_rate_id,
                vat_rate=selected_vat_rate.rate if selected_vat_rate else 24,  # Fallback
                status=form.status.data,
                payment_terms=form.payment_terms.data,
                client_extra_info=form.client_extra_info.data,
                note=form.note.data,
                note_label_id=int(request.form.get('selected_note_label_id')) if request.form.get('selected_note_label_id') else None,
                announcements=form.announcements.data,
                pdf_template=form.pdf_template.data or 'standard'
            )
            
            try:
                db.session.add(invoice)
                db.session.flush()  # Get invoice ID
                
                # Add invoice lines (use valid_lines instead of form.lines)
                for line_form in valid_lines:
                    # Use .data attribute to access the form data since FormField objects are corrupted
                    line_data = line_form.data
                    
                    # Use user-provided line_total if available, otherwise calculate
                    if line_data.get('line_total') is not None and line_data['line_total'] != '':
                        line_total = float(line_data['line_total'])
                        logger.debug(f"Using user-provided line total: {line_total}")
                    else:
                        line_total = calculate_line_total(line_data['qty'], line_data['unit_price'])
                        logger.debug(f"Calculated line total: {line_total}")
                    
                    line = InvoiceLine(
                        invoice_id=invoice.id,
                        description=line_data['description'],
                        qty=line_data['qty'],
                        unit_price=line_data['unit_price'],
                        line_total=line_total
                    )
                    db.session.add(line)
                
                db.session.flush()  # Ensure lines are saved
                
                # Calculate totals
                calculate_invoice_totals(invoice)
                
                db.session.commit()
                
                # Refresh invoice to ensure computed properties reflect calculated values
                try:
                    db.session.refresh(invoice)
                except Exception as refresh_error:
                    logger.warning(f"Could not refresh new invoice {invoice.id}: {refresh_error}")
                
                flash(f'Arve "{invoice.number}" on edukalt loodud.', 'success')
                logger.info(f"Invoice {invoice.number} created successfully with {len(valid_lines)} lines")
                return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
            except Exception as e:
                logger.error(f"Error creating invoice: {str(e)}")
                db.session.rollback()
                flash('Arve loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    else:
        if request.method == 'POST':
            logger.debug("Form validation failed")
    
    # Ensure at least one line form
    if not form.lines.entries:
        form.lines.append_entry()
    # Get payment terms for JavaScript
    try:
        payment_terms = PaymentTerms.get_active_terms()
    except:
        payment_terms = []
    
    # Get note labels
    try:
        note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
        # For new invoices, don't pre-select any note label
        default_note_label_id = None
        
        # Create default labels if none exist
        if not note_labels:
            NoteLabel.create_default_labels()
            note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
            # Keep default_note_label_id as None for new invoices
            
    except Exception as e:
        logger.error(f"Error getting note labels: {e}")
        # Fallback data
        note_labels = []
        default_note_label_id = None
    
    # Get current VAT rate object for template display
    current_vat_rate = None
    if form.vat_rate_id.data:
        current_vat_rate = VatRate.query.get(form.vat_rate_id.data)
    
    return render_template('invoice_form.html', form=form, title='Uus arve', clients=clients, vat_rates=vat_rates, payment_terms=payment_terms, note_labels=note_labels, default_note_label_id=default_note_label_id, current_vat_rate=current_vat_rate)


@invoices_bp.route('/invoices/<int:invoice_id>')
def view_invoice(invoice_id):
    """View invoice details."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Get note label for this invoice
    try:
        logger.debug(f"HTML route - Invoice {invoice.id} note_label_id: {invoice.note_label_id}")
        if invoice.note_label_id:
            # Get the note label directly
            note_label_obj = NoteLabel.query.get(invoice.note_label_id)
            if note_label_obj:
                note_label_text = note_label_obj.name
                logger.debug(f"HTML route - Using invoice-specific note label: {note_label_text}")
            else:
                # Fallback if note label not found
                note_label_text = "Märkus"
                logger.debug(f"HTML route - Note label not found, using fallback")
        else:
            # Use default label
            note_label = NoteLabel.get_default_label()
            note_label_text = note_label.name if note_label else "Märkus"
            logger.debug(f"HTML route - Using default note label: {note_label_text}")
    except Exception as e:
        logger.error(f"HTML route - Error getting note label: {e}")
        note_label_text = "Märkus"
    
    return render_template('invoice_detail.html', invoice=invoice, note_label=note_label_text)


@invoices_bp.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    """Edit invoice."""
    # For GET requests, ensure we get fresh data by expunging any cached instances
    if request.method == 'GET':
        # Remove any cached invoice instances from session to avoid stale relationship data
        try:
            cached_invoice = db.session.get(Invoice, invoice_id)
            if cached_invoice:
                db.session.expunge(cached_invoice)
                logger.debug(f"Expunged cached invoice {invoice_id} from session")
        except Exception as e:
            logger.debug(f"No cached invoice to expunge: {e}")
    
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # For GET requests, ensure relationships are fresh by explicitly loading them
    if request.method == 'GET':
        # Force reload of lines relationship to ensure we have current data
        db.session.refresh(invoice)
        # Explicitly access the relationship to force loading
        _ = len(invoice.lines)
        logger.debug(f"Refreshed invoice {invoice_id} and loaded {len(invoice.lines)} lines")
    
    # Allow editing all invoices (business requirement for flexibility)
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    
    # Populate payment terms choices BEFORE creating form
    try:
        from app.models import PaymentTerms
        payment_terms_choices = [('', 'Vali makse tingimus...')] + PaymentTerms.get_choices()
    except Exception as e:
        logger.error(f"Error loading payment terms: {e}")
        # Fallback to static choices if PaymentTerms table doesn't exist yet
        payment_terms_choices = [('', 'Vali makse tingimus...'), ('14 päeva', '14 päeva')]
    
    logger.debug(f"Payment terms choices: {payment_terms_choices}")
    
    # Create form and set choices IMMEDIATELY
    form = InvoiceForm()
    form.client_id.choices = [(c.id, c.name) for c in clients]
    form.payment_terms.choices = payment_terms_choices
    
    # Set invoice ID for unique validation
    form._invoice_id = invoice_id
    
    # Populate VAT rate choices
    vat_rates = VatRate.get_active_rates()
    
    # Set current VAT rate - with debugging
    logger.debug(f"GET request - Invoice VAT rate: {invoice.vat_rate}% (ID: {invoice.vat_rate_id})")
    if invoice.vat_rate_id:
        form.vat_rate_id.data = invoice.vat_rate_id
        logger.debug(f"GET request - Set form VAT rate ID to: {invoice.vat_rate_id}")
    else:
        # Fallback: try to find matching rate by value
        matching_rate = VatRate.query.filter_by(rate=invoice.vat_rate, is_active=True).first()
        if matching_rate:
            form.vat_rate_id.data = matching_rate.id
            logger.debug(f"GET request - Found matching rate for {invoice.vat_rate}%: ID {matching_rate.id}")
        else:
            # CRITICAL FIX: Instead of defaulting to first rate, preserve existing VAT rate value
            # Find or create a matching VAT rate for the current invoice's rate
            existing_vat_rate = VatRate.query.filter_by(rate=invoice.vat_rate).first()
            if existing_vat_rate:
                form.vat_rate_id.data = existing_vat_rate.id
                logger.debug(f"GET request - Found inactive matching rate for {invoice.vat_rate}%: ID {existing_vat_rate.id}")
            else:
                # Log warning but don't set a default that changes user's intended VAT rate
                logger.warning(f"GET request - No matching VAT rate found for {invoice.vat_rate}%, keeping existing value")
                # Set to empty to force user to make a conscious choice
                form.vat_rate_id.data = None
    
    # Always populate form with current invoice data - ONLY for GET requests
    if request.method == 'GET':
        form.number.data = invoice.number
        form.client_id.data = invoice.client_id  
        form.date.data = invoice.date
        form.due_date.data = invoice.due_date
        form.status.data = invoice.status
        form.payment_terms.data = invoice.payment_terms
        form.client_extra_info.data = invoice.client_extra_info
        form.note.data = invoice.note
        form.announcements.data = invoice.announcements
        form.pdf_template.data = invoice.pdf_template or 'standard'
    
    # Populate existing lines - ONLY on GET requests to avoid losing user input
    # This is critical to preserve user data during validation failures
    if request.method == 'GET':
        # Clear any existing entries
        while len(form.lines) > 0:
            form.lines.pop_entry()
        
        # Add existing invoice lines - create form data dictionary and let WTForms handle it
        for line in invoice.lines:
            # Create form entry
            line_form = form.lines.append_entry()
            
            # Populate with line data - this ensures fields are properly initialized
            line_data = {
                'id': str(line.id),  # Keep as string to match form field expectations
                'description': line.description,
                'qty': line.qty,
                'unit_price': line.unit_price,
                'line_total': line.line_total
            }
            
            # Use process method to properly initialize the form fields
            try:
                line_form.process(formdata=None, data=line_data)
                logger.debug(f"Successfully populated line {line.id}: {line.description}")
            except Exception as e:
                logger.error(f"Error processing line {line.id} data: {e}")
                # Safe fallback: set field data without overwriting field objects
                try:
                    if hasattr(line_form.id, 'data'):
                        line_form.id.data = str(line.id)
                    if hasattr(line_form.description, 'data'):
                        line_form.description.data = line.description  
                    if hasattr(line_form.qty, 'data'):
                        line_form.qty.data = float(line.qty)
                    if hasattr(line_form.unit_price, 'data'):
                        line_form.unit_price.data = float(line.unit_price)
                    if hasattr(line_form.line_total, 'data'):
                        line_form.line_total.data = float(line.line_total)
                    logger.debug(f"Fallback populated line {line.id}")
                except Exception as e2:
                    logger.error(f"Fallback failed for line {line.id}: {e2}")
                    # Last resort: create new form entry
                    logger.warning(f"Creating fresh form entry for line {line.id}")
        
        # Ensure at least one line exists for new invoices or if no lines
        if not form.lines.entries:
            form.lines.append_entry()
            logger.debug("Added empty line entry for form")
    
    # For POST requests, the form data comes from request and should not be overwritten
    
    # Enhanced debugging for line population
    logger.debug(f"Edit invoice {invoice_id} - Method: {request.method}, Form lines: {len(form.lines.entries)}")
    if request.method == 'GET':
        logger.debug(f"Database has {len(invoice.lines)} lines for invoice {invoice_id}")
        for i, line in enumerate(invoice.lines):
            logger.debug(f"  Line {i}: ID={line.id}, desc='{line.description[:30]}...', qty={line.qty}, price={line.unit_price}")
    
    # Log form line entries after population
    for i, line_form in enumerate(form.lines.entries):
        try:
            # First try direct field access
            desc = line_form.description.data if hasattr(line_form.description, 'data') else 'NO_DATA'
            qty = line_form.qty.data if hasattr(line_form.qty, 'data') else 'NO_DATA' 
            price = line_form.unit_price.data if hasattr(line_form.unit_price, 'data') else 'NO_DATA'
            line_id = line_form.id.data if hasattr(line_form.id, 'data') else 'NO_DATA'
            logger.debug(f"  Form line {i}: ID={line_id}, desc='{desc}', qty={qty}, price={price}")
        except Exception as e:
            logger.debug(f"  Form line {i}: Error accessing fields - {e}")
        
        # Also log the data dictionary access
        try:
            data_dict = getattr(line_form, 'data', {})
            logger.debug(f"  Form line {i} data dict: {data_dict}")
        except Exception as e:
            logger.debug(f"  Form line {i}: Error accessing data dict - {e}")
    
    # Debug form validation
    if request.method == 'POST':
        logger.debug(f"POST data received for payment_terms: '{request.form.get('payment_terms')}'")
        logger.debug(f"Form payment_terms choices: {form.payment_terms.choices}")
        logger.debug(f"Current form payment_terms data: '{form.payment_terms.data}'")
    
    if form.validate_on_submit():
        logger.debug(f"Form validation successful for invoice {invoice_id}")
        logger.debug(f"Form data received - due_date: {form.due_date.data}, client_extra_info: '{form.client_extra_info.data}', note: '{form.note.data}', announcements: '{form.announcements.data}', payment_terms: '{form.payment_terms.data}'")
        
        # Debug VAT rate handling
        logger.debug(f"VAT rate form data: {form.vat_rate_id.data}")
        logger.debug(f"Raw form VAT rate: {request.form.get('vat_rate_id')}")
        logger.debug(f"Current invoice VAT rate: {invoice.vat_rate}% (ID: {invoice.vat_rate_id})")
        
        # Custom validation: check if form has at least one complete line
        valid_lines_count = 0
        for line_form in form.lines.entries:
            try:
                description = line_form.description.data.strip() if line_form.description.data else ''
                qty = line_form.qty.data
                unit_price = line_form.unit_price.data
                
                if description and qty is not None and unit_price is not None:
                    valid_lines_count += 1
            except AttributeError:
                # Fallback to data dict access
                try:
                    line_data = line_form.data if hasattr(line_form, 'data') else {}
                    description = line_data.get('description', '').strip()
                    qty = line_data.get('qty')
                    unit_price = line_data.get('unit_price')
                    
                    if description and qty is not None and unit_price is not None:
                        valid_lines_count += 1
                except:
                    continue
        
        if valid_lines_count == 0:
            flash('Palun lisa vähemalt üks täielik arve rida.', 'warning')
        else:
            # Update invoice fields - with debug logging
            logger.debug(f"Updating invoice {invoice_id} fields:")
            logger.debug(f"  Old due_date: {invoice.due_date}, New due_date: {form.due_date.data}")
            logger.debug(f"  Old client_extra_info: '{invoice.client_extra_info}', New client_extra_info: '{form.client_extra_info.data}'")
            logger.debug(f"  Old note: '{invoice.note}', New note: '{form.note.data}'")
            logger.debug(f"  Old announcements: '{invoice.announcements}', New announcements: '{form.announcements.data}'")
            logger.debug(f"  Old payment_terms: '{invoice.payment_terms}', New payment_terms: '{form.payment_terms.data}'")
            
            invoice.number = form.number.data
            invoice.client_id = form.client_id.data
            invoice.date = form.date.data
            invoice.due_date = form.due_date.data
            
            # Update VAT rate (convert string to int) - with proper validation
            logger.debug(f"VAT rate update - Current: {invoice.vat_rate}% (ID: {invoice.vat_rate_id})")
            logger.debug(f"VAT rate update - Form submitted: '{request.form.get('vat_rate_id')}'")
            
            try:
                # CRITICAL FIX: Use raw form data directly to avoid form processing issues
                # The previous bug was using form.vat_rate_id.data which could be stale
                vat_rate_id_raw = request.form.get('vat_rate_id')
                vat_rate_id = int(vat_rate_id_raw) if vat_rate_id_raw else None
                
                if vat_rate_id is not None:
                    selected_vat_rate = VatRate.query.get(vat_rate_id)
                    if selected_vat_rate:
                        old_vat_rate = invoice.vat_rate
                        old_vat_rate_id = invoice.vat_rate_id
                        
                        # Update both VAT rate fields
                        invoice.vat_rate_id = vat_rate_id
                        invoice.vat_rate = selected_vat_rate.rate
                        
                        logger.info(f"VAT rate updated: {old_vat_rate}% (ID: {old_vat_rate_id}) -> {selected_vat_rate.rate}% (ID: {vat_rate_id})")
                    else:
                        logger.error(f"VAT rate with ID {vat_rate_id} not found in database")
                        # Keep existing values if the new one is invalid
                else:
                    logger.debug("No VAT rate ID provided, keeping existing values")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid VAT rate ID '{vat_rate_id_raw}': {e}")
                # Keep existing VAT rate if conversion fails
            
            invoice.status = form.status.data
            # Handle None values - convert empty strings to None for database storage
            invoice.payment_terms = form.payment_terms.data if form.payment_terms.data and form.payment_terms.data.strip() else None
            invoice.client_extra_info = form.client_extra_info.data if form.client_extra_info.data and form.client_extra_info.data.strip() else None
            invoice.note = form.note.data if form.note.data and form.note.data.strip() else None
            selected_note_label_id = request.form.get('selected_note_label_id')
            logger.debug(f"Selected note label ID from form: {selected_note_label_id}")
            invoice.note_label_id = int(selected_note_label_id) if selected_note_label_id else None
            invoice.announcements = form.announcements.data if form.announcements.data and form.announcements.data.strip() else None
            invoice.pdf_template = form.pdf_template.data or 'standard'
            
            logger.debug(f"After update:")
            logger.debug(f"  due_date: {invoice.due_date}")
            logger.debug(f"  client_extra_info: '{invoice.client_extra_info}'")
            logger.debug(f"  note: '{invoice.note}'")
            logger.debug(f"  announcements: '{invoice.announcements}'")
            logger.debug(f"  payment_terms: '{invoice.payment_terms}'")
            
            try:
                # Get existing line IDs and collect form data
                existing_line_ids = [line.id for line in invoice.lines]
                processed_line_ids = []
                
                # Process form lines and collect valid ones
                valid_form_lines = []
                for line_form in form.lines.entries:
                    try:
                        description = line_form.description.data.strip() if line_form.description.data else ''
                        qty = line_form.qty.data
                        unit_price = line_form.unit_price.data
                        line_total = line_form.line_total.data
                        line_id = line_form.id.data
                    except AttributeError:
                        # Fallback to data dict access
                        try:
                            line_data = line_form.data if hasattr(line_form, 'data') else {}
                            description = line_data.get('description', '').strip()
                            qty = line_data.get('qty')
                            unit_price = line_data.get('unit_price')
                            line_total = line_data.get('line_total')
                            line_id = line_data.get('id')
                        except:
                            continue  # Skip invalid lines
                    
                    # Only process lines with complete data
                    if description and qty is not None and unit_price is not None:
                        valid_form_lines.append({
                            'id': line_id,
                            'description': description,
                            'qty': qty,
                            'unit_price': unit_price,
                            'line_total': line_total
                        })
                        
                        if line_id:
                            try:
                                processed_line_ids.append(int(line_id))
                            except (ValueError, TypeError):
                                pass  # Invalid ID, treat as new line
                
                # Delete lines that were removed from the form
                for line_id in existing_line_ids:
                    if line_id not in processed_line_ids:
                        line_to_delete = InvoiceLine.query.get(line_id)
                        if line_to_delete and line_to_delete.invoice_id == invoice.id:
                            db.session.delete(line_to_delete)
                            logger.debug(f"Deleted line {line_id}")
                
                # Update or create lines
                for line_data in valid_form_lines:
                    # Use user-provided line_total if available, otherwise calculate
                    if line_data.get('line_total') is not None and line_data['line_total'] != '':
                        line_total = float(line_data['line_total'])
                        logger.debug(f"Using user-provided line total: {line_total}")
                    else:
                        line_total = calculate_line_total(line_data['qty'], line_data['unit_price'])
                        logger.debug(f"Calculated line total: {line_total}")
                    
                    if line_data['id']:
                        # Update existing line
                        try:
                            line_id = int(line_data['id'])
                            line = InvoiceLine.query.get(line_id)
                            if line and line.invoice_id == invoice.id:
                                line.description = line_data['description']
                                line.qty = line_data['qty']
                                line.unit_price = line_data['unit_price']
                                line.line_total = line_total
                                logger.debug(f"Updated line {line_id}")
                        except (ValueError, TypeError):
                            # Invalid ID, create new line instead
                            line = InvoiceLine(
                                invoice_id=invoice.id,
                                description=line_data['description'],
                                qty=line_data['qty'],
                                unit_price=line_data['unit_price'],
                                line_total=line_total
                            )
                            db.session.add(line)
                            logger.debug("Created new line (invalid ID)")
                    else:
                        # Create new line
                        line = InvoiceLine(
                            invoice_id=invoice.id,
                            description=line_data['description'],
                            qty=line_data['qty'],
                            unit_price=line_data['unit_price'],
                            line_total=line_total
                        )
                        db.session.add(line)
                        logger.debug("Created new line")
                
                # Flush to ensure all line operations are complete
                db.session.flush()
                
                # Refresh the invoice.lines relationship to see the updated lines
                db.session.refresh(invoice, ['lines'])
                
                # Recalculate totals after all line updates
                calculate_invoice_totals(invoice)
                
                # Final commit
                db.session.commit()
                
                # Refresh invoice to ensure computed properties reflect updated values
                try:
                    db.session.refresh(invoice)
                except Exception as refresh_error:
                    logger.warning(f"Could not refresh invoice {invoice_id} after update: {refresh_error}")
                    # Continue with redirect since the data is already committed
                
                logger.info(f"Successfully updated invoice {invoice_id} with {len(valid_form_lines)} lines")
                flash(f'Arve "{invoice.number}" on edukalt uuendatud.', 'success')
                return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
                
            except Exception as e:
                logger.error(f"Error updating invoice {invoice_id}: {str(e)}")
                logger.error(f"Exception type: {type(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                db.session.rollback()
                flash('Arve uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
    else:
        if request.method == 'POST':
            logger.error("Form validation failed for invoice edit")
            logger.error(f"Form errors: {form.errors}")
            # Check individual field errors
            for field_name, field_errors in form.errors.items():
                for error in field_errors:
                    logger.error(f"Field '{field_name}': {error}")
            # Don't flash error message here - let the form handle it
    
    # Get payment terms for JavaScript
    try:
        payment_terms = PaymentTerms.get_active_terms()
    except:
        payment_terms = []
    
    # Get note labels
    try:
        note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
        
        # For edit mode, only pre-select if this is a GET request (initial load)
        # On POST requests (form submission), respect user's current selection
        if request.method == 'GET' and invoice.note_label_id:
            default_note_label_id = invoice.note_label_id
        else:
            # Don't pre-select anything, let form maintain its state
            default_note_label_id = None
        
        # Create default labels if none exist
        if not note_labels:
            NoteLabel.create_default_labels()
            note_labels = NoteLabel.query.filter_by(is_active=True).order_by(NoteLabel.name).all()
            if not invoice.note_label_id:
                default_note_label = NoteLabel.get_default_label()
                default_note_label_id = default_note_label.id if default_note_label else None
            
    except Exception as e:
        logger.error(f"Error getting note labels: {e}")
        # Fallback data
        note_labels = []
        default_note_label_id = invoice.note_label_id if invoice.note_label_id else None
    
    # Get current VAT rate object for template display
    current_vat_rate = None
    if request.method == 'GET':
        # For GET requests, use the form data (which was set from invoice)
        if form.vat_rate_id.data:
            current_vat_rate = VatRate.query.get(form.vat_rate_id.data)
    else:
        # For POST requests (validation errors), use the current invoice VAT rate
        if invoice.vat_rate_id:
            current_vat_rate = VatRate.query.get(invoice.vat_rate_id)
    
    return render_template('invoice_form.html', form=form, invoice=invoice, title='Muuda arvet', clients=clients, vat_rates=vat_rates, payment_terms=payment_terms, note_labels=note_labels, default_note_label_id=default_note_label_id, current_vat_rate=current_vat_rate)


@invoices_bp.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
def delete_invoice(invoice_id):
    """Delete invoice."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Allow deleting all invoices (business requirement for flexibility)
    
    try:
        invoice_number = invoice.number
        db.session.delete(invoice)
        db.session.commit()
        flash(f'Arve "{invoice_number}" on edukalt kustutatud.', 'success')
        return redirect(url_for('invoices.invoices'))
    except Exception as e:
        logger.error(f"Error deleting invoice {invoice_id}: {str(e)}")
        db.session.rollback()
        flash('Arve kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/status/<new_status>', methods=['POST'])
def change_status(invoice_id, new_status):
    """Change invoice status using the status transition service.
    
    Supports both regular POST requests and AJAX requests.
    - AJAX requests return JSON response
    - Regular POST requests redirect to invoice list
    """
    
    invoice = Invoice.query.get_or_404(invoice_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        # Use the status transition service
        success, message = InvoiceStatusTransition.transition_invoice_status(invoice, new_status)
        
        if success:
            db.session.commit()
            
            # For AJAX requests, return JSON response
            if is_ajax:
                # Generate the new badge HTML
                badge_html = f'<span class="badge bg-{invoice.status_color} text-white clickable-status" data-invoice-id="{invoice.id}" style="cursor: pointer;">{invoice.status_display}</span>'
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'new_status': invoice.status,
                    'status_display': invoice.status_display,
                    'status_color': invoice.status_color,
                    'badge_html': badge_html
                })
            else:
                flash(message, 'success')
        else:
            if is_ajax:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400
            else:
                flash(message, 'warning')
            
    except Exception as e:
        logger.error(f"Error changing status for invoice {invoice_id} to {new_status}: {str(e)}")
        db.session.rollback()
        error_message = 'Staatuse muutmisel tekkis viga. Palun proovi uuesti.'
        
        if is_ajax:
            return jsonify({
                'success': False,
                'message': error_message
            }), 500
        else:
            flash(error_message, 'danger')
    
    # For regular POST requests, redirect to invoice list instead of individual invoice
    return redirect(url_for('invoices.invoices'))


@invoices_bp.route('/invoices/<int:invoice_id>/duplicate', methods=['POST'])
def duplicate_invoice(invoice_id):
    """Duplicate invoice."""
    original = Invoice.query.get_or_404(invoice_id)
    
    try:
        # Generate new invoice number
        new_number = generate_invoice_number()
        
        # Create duplicate invoice
        duplicate = Invoice(
            number=new_number,
            client_id=original.client_id,
            date=date.today(),  # Use today's date
            due_date=original.due_date,
            vat_rate_id=original.vat_rate_id,
            vat_rate=original.vat_rate,
            payment_terms=original.payment_terms,
            client_extra_info=original.client_extra_info,
            note=original.note,
            note_label_id=original.note_label_id,  # Copy note label selection
            announcements=original.announcements,
            pdf_template=original.pdf_template,
            status='maksmata'  # Always create as unpaid
        )
        
        db.session.add(duplicate)
        db.session.flush()  # Get invoice ID
        
        # Duplicate invoice lines
        for original_line in original.lines:
            line = InvoiceLine(
                invoice_id=duplicate.id,
                description=original_line.description,
                qty=original_line.qty,
                unit_price=original_line.unit_price,
                line_total=original_line.line_total
            )
            db.session.add(line)
        
        db.session.flush()
        
        # Calculate totals
        calculate_invoice_totals(duplicate)
        
        db.session.commit()
        
        # Refresh invoice to ensure computed properties reflect calculated values
        try:
            db.session.refresh(duplicate)
        except Exception as refresh_error:
            logger.warning(f"Could not refresh duplicated invoice {duplicate.id}: {refresh_error}")
        
        flash(f'Arve on edukalt dubleeritud uue numbriga "{new_number}".', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=duplicate.id))
    except Exception as e:
        logger.error(f"Error duplicating invoice {invoice_id}: {str(e)}")
        db.session.rollback()
        flash('Arve dubleerimisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/email', methods=['POST'])
def email_invoice(invoice_id):
    """Send invoice via email."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if client has email
    if not invoice.client.email:
        flash('Kliendil ei ole e-maili aadressi määratud.', 'warning')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    try:
        # Here you would implement actual email sending
        # In the new 2-status system, sending an email doesn't change the status
        # Invoice remains 'maksmata' until payment is received
        
        flash(f'Arve "{invoice.number}" on edukalt saadetud e-mailile {invoice.client.email}.', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    except Exception as e:
        logger.error(f"Error sending invoice {invoice_id} via email: {str(e)}")
        db.session.rollback()
        flash('Arve saatmisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))