from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import db, Client, Invoice
from app.forms import ClientForm, ClientSearchForm
from app.logging_config import get_logger
from sqlalchemy import or_

logger = get_logger(__name__)

clients_bp = Blueprint('clients', __name__)


@clients_bp.route('/clients')
def clients():
    """Clients management page with search and filtering."""
    search_form = ClientSearchForm()
    search_query = request.args.get('search', '').strip()
    
    # Pagination parameters with validation
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
    
    # Build query
    query = Client.query
    
    if search_query:
        query = query.filter(
            or_(
                Client.name.ilike(f'%{search_query}%'),
                Client.email.ilike(f'%{search_query}%'),
                Client.registry_code.ilike(f'%{search_query}%')
            )
        )
    
    # Order by name
    query = query.order_by(Client.name.asc())
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    clients_list = query.offset(offset).limit(per_page).all()
    
    # Prepare client data with statistics
    clients_data = []
    for client in clients_list:
        clients_data.append({
            'id': client.id,
            'name': client.name,
            'registry_code': client.registry_code,
            'email': client.email,
            'phone': client.phone,
            'invoices': client.invoice_count,
            'last': client.last_invoice_date.strftime('%Y-%m-%d') if client.last_invoice_date else None,
            'total_revenue': float(client.total_revenue)
        })
    
    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page
    start_item = offset + 1 if clients_list else 0
    end_item = min(offset + per_page, total_count)
    
    # Get all clients for statistics (only if we need global stats)
    all_clients = Client.query.all()
    
    return render_template('clients.html', 
                         clients=clients_data, 
                         search_form=search_form,
                         search_query=search_query,
                         # Pagination data
                         current_page=page,
                         per_page=per_page,
                         total_count=total_count,
                         total_pages=total_pages,
                         start_item=start_item,
                         end_item=end_item,
                         # Global statistics
                         all_clients=all_clients)


@clients_bp.route('/clients/new', methods=['GET', 'POST'])
def new_client():
    """Create new client."""
    if request.method == 'POST':
        form = ClientForm()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        
        if form.validate_on_submit():
            # Create client
            client = Client(
                name=form.name.data,
                registry_code=form.registry_code.data if form.registry_code.data else None,
                email=form.email.data if form.email.data else None,
                phone=form.phone.data if form.phone.data else None,
                address=form.address.data if form.address.data else None
            )
            
            try:
                db.session.add(client)
                db.session.commit()
                
                if is_ajax:
                    return jsonify({
                        'success': True, 
                        'message': f'Klient "{client.name}" on edukalt loodud.'
                    })
                
                flash(f'Klient "{client.name}" on edukalt loodud.', 'success')
                return redirect(url_for('clients.clients'))
                
            except Exception:
                db.session.rollback()
                
                if is_ajax:
                    return jsonify({'success': False, 'error': 'Andmebaasi viga. Palun proovi uuesti.'}), 500
                
                flash('Kliendi loomisel tekkis viga. Palun proovi uuesti.', 'danger')
                return redirect(url_for('clients.clients'))
        else:
            # Validation failed
            if is_ajax:
                errors = []
                for field, field_errors in form.errors.items():
                    errors.extend(field_errors)
                error_msg = ', '.join(errors) if errors else 'Palun kontrolli andmeid.'
                return jsonify({'success': False, 'error': error_msg}), 400
            
            # Non-AJAX - show errors in template
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
            return render_template('client_form.html', form=form, title='Uus klient')
    
    # GET request - show form
    form = ClientForm()
    return render_template('client_form.html', form=form, title='Uus klient')


@clients_bp.route('/clients/<int:client_id>')
def view_client(client_id):
    """View client details."""
    client = Client.query.get_or_404(client_id)
    
    # Get client's invoices
    invoices = Invoice.query.filter_by(client_id=client_id).order_by(Invoice.date.desc()).all()
    
    return render_template('client_detail.html', client=client, invoices=invoices)


@clients_bp.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    """Edit client."""
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    
    if form.validate_on_submit():
        client.name = form.name.data
        client.registry_code = form.registry_code.data if form.registry_code.data else None
        client.email = form.email.data if form.email.data else None
        client.phone = form.phone.data if form.phone.data else None
        client.address = form.address.data if form.address.data else None
        
        try:
            db.session.commit()
            flash(f'Klient "{client.name}" on edukalt uuendatud.', 'success')
            return redirect(url_for('clients.view_client', client_id=client.id))
        except Exception:
            db.session.rollback()
            flash('Kliendi uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('client_form.html', form=form, client=client, title='Muuda klienti')


@clients_bp.route('/clients/<int:client_id>/delete', methods=['POST'])
def delete_client(client_id):
    """Delete client."""
    client = Client.query.get_or_404(client_id)
    
    # Check if client has invoices
    if client.invoices:
        flash(f'Klienti "{client.name}" ei saa kustutada, kuna tal on arveid.', 'warning')
        return redirect(url_for('clients.view_client', client_id=client_id))
    
    try:
        client_name = client.name
        db.session.delete(client)
        db.session.commit()
        flash(f'Klient "{client_name}" on edukalt kustutatud.', 'success')
        return redirect(url_for('clients.clients'))
    except Exception:
        db.session.rollback()
        flash('Kliendi kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('clients.view_client', client_id=client_id))


@clients_bp.route('/api/clients')
def api_clients():
    """API endpoint for client list (for dropdowns etc)."""
    clients_list = Client.query.order_by(Client.name.asc()).all()
    return jsonify([{
        'id': client.id,
        'name': client.name,
        'email': client.email
    } for client in clients_list])


