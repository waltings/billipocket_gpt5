from flask import Flask, url_for, render_template, request, redirect, jsonify, flash
import os
import click
from datetime import date, timedelta, datetime
from app.logging_config import setup_logging


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Get the base directory (project root)
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(basedir, 'static'))
    
    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    from app.models import db
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    from flask_login import LoginManager
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    
    db.init_app(app)
    
    # Initialize CSRF protection 
    csrf = CSRFProtect(app)
    
    # Initialize Flask-Limiter
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Palun logi sisse, et jätkata.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Setup logging
    setup_logging(app)
    
    # Enhanced security headers
    @app.after_request
    def set_security_headers(response):
        # Basic security headers (always applied)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Production-specific security headers
        if not app.config.get('DEBUG'):
            # Strict Transport Security (HTTPS only)
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            # Content Security Policy
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
            response.headers['Content-Security-Policy'] = csp
            
            # Permissions Policy
            response.headers['Permissions-Policy'] = (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        
        # Session security
        if response.headers.get('Set-Cookie'):
            # Enhance cookie security
            response.headers['Set-Cookie'] = response.headers['Set-Cookie'].replace(
                'HttpOnly;', 'HttpOnly; SameSite=Lax; Secure;'
            ) if not app.config.get('DEBUG') else response.headers['Set-Cookie'].replace(
                'HttpOnly;', 'HttpOnly; SameSite=Lax;'
            )
        
        return response
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    @app.errorhandler(400)
    def csrf_error(error):
        from flask_wtf.csrf import CSRFError
        if isinstance(error, CSRFError):
            return render_template('400.html', 
                                 error_message='CSRF token on puudu või vigane. Palun proovi uuesti.'), 400
        return render_template('400.html'), 400
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        """Handle rate limiting errors."""
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Liiga palju päringuid. Palun proovi hiljem uuesti.',
                'retry_after': getattr(error, 'retry_after', 900)
            }), 429
        else:
            flash('Liiga palju päringuid. Palun proovi hiljem uuesti.', 'warning')
            from app.forms import LoginForm
            return render_template('auth/login.html', form=LoginForm()), 429
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        """Handle unauthorized access."""
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Autentimine ebaõnnestus. Palun logi sisse.'
            }), 401
        else:
            flash('Palun logi sisse, et jätkata.', 'info')
            return redirect(url_for('auth.login'))
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle forbidden access."""
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Sul puudub õigus sellele toimingule.'
            }), 403
        else:
            flash('Sul puudub õigus sellele toimingule.', 'danger')
            return redirect(url_for('dashboard.overview'))
    
    # Global context processor for navigation
    @app.context_processor
    def inject_nav():
        try:
            return {
                "nav": {
                    "overview": url_for('dashboard.overview'),
                    "invoices": url_for('invoices.invoices'),
                    "clients": url_for('clients.clients'),
                    "reports": url_for('dashboard.reports'),
                    "settings": url_for('dashboard.settings'),
                }
            }
        except RuntimeError:
            # Return empty nav when outside request context (e.g., PDF generation)
            return {"nav": {}}
    
    # Make CSRF token available in templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)
    
    # Enhanced flash message handling for modern frontend
    @app.context_processor
    def inject_flash_messages():
        """Inject categorized flash messages for better frontend handling."""
        from flask import get_flashed_messages
        
        # Get all flash messages with categories
        messages = get_flashed_messages(with_categories=True)
        
        # Organize messages by category for frontend consumption
        categorized_messages = {
            'success': [],
            'info': [],
            'warning': [],
            'danger': [],
            'error': []
        }
        
        for category, message in messages:
            # Map 'error' to 'danger' for consistency
            if category == 'error':
                category = 'danger'
            
            if category in categorized_messages:
                categorized_messages[category].append({
                    'text': message,
                    'category': category,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return dict(flash_messages=categorized_messages)
    
    # API endpoint to get flash messages as JSON
    @app.route('/api/messages')
    def api_flash_messages():
        """Get current flash messages as JSON and clear them."""
        from flask import get_flashed_messages
        
        messages = get_flashed_messages(with_categories=True)
        
        formatted_messages = []
        for category, message in messages:
            formatted_messages.append({
                'text': message,
                'category': 'danger' if category == 'error' else category,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'messages': formatted_messages
        }), 200
    
    # Custom template filters
    @app.template_filter('currency')
    def currency_filter(value):
        """Format number with thousand separators for better readability."""
        if value is None:
            return '0.00'
        try:
            return f"{float(value):,.2f}".replace(',', ' ')
        except (ValueError, TypeError):
            return '0.00'
    
    @app.template_filter('quantity')
    def quantity_filter(value):
        """Format quantity - show decimals only when needed."""
        if value is None:
            return '0'
        try:
            num = float(value)
            # If it's a whole number, don't show decimal places
            if num == int(num):
                return str(int(num))
            else:
                # Show up to 2 decimal places, but strip trailing zeros
                return f"{num:.2f}".rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return '0'
    
    @app.template_filter('vat_rate')
    def vat_rate_filter(value):
        """Format VAT rate - show decimals only when needed."""
        if value is None:
            return '0'
        try:
            num = float(value)
            # If it's a whole number, don't show decimal places
            if num == int(num):
                return str(int(num))
            else:
                # Show up to 2 decimal places, but strip trailing zeros
                return f"{num:.2f}".rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return '0'
    
    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.clients import clients_bp
    from app.routes.invoices import invoices_bp
    from app.routes.pdf import pdf_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(auth_bp)
    
    # CLI commands
    @app.cli.command()
    def init_db():
        """Initialize the database."""
        with app.app_context():
            db.create_all()
            click.echo('Database tables created successfully.')
    
    @app.cli.command()
    def seed_data():
        """Seed the database with sample data."""
        with app.app_context():
            from app.models import Client, Invoice, InvoiceLine, VatRate
            
            # Check if data already exists
            if Client.query.count() > 0:
                click.echo('Sample data already exists. Skipping...')
                return
            
            # First ensure VAT rates exist (this checks for duplicates internally)
            standard_vat = VatRate.get_default_rate()
            if not standard_vat:
                VatRate.create_default_rates()
                standard_vat = VatRate.get_default_rate()
            
            # Create sample clients
            client1 = Client(
                name='Nordics OÜ',
                registry_code='12345678',
                email='info@nordics.ee',
                phone='+372 5555 1234',
                address='Tallinn, Estonia'
            )
            client2 = Client(
                name='Viridian AS',
                registry_code='87654321',
                email='contact@viridian.ee',
                phone='+372 5555 5678',
                address='Tartu, Estonia'
            )
            
            db.session.add(client1)
            db.session.add(client2)
            db.session.flush()  # Get IDs
            
            # Create sample invoices
            invoice1 = Invoice(
                number='2025-0001',
                client_id=client1.id,
                date=date(2025, 8, 10),
                due_date=date(2025, 8, 24),
                vat_rate_id=standard_vat.id if standard_vat else None,
                vat_rate=standard_vat.rate if standard_vat else 24,
                status='maksmata'
            )
            invoice2 = Invoice(
                number='2025-0002',
                client_id=client2.id,
                date=date(2025, 8, 8),
                due_date=date(2025, 8, 22),
                vat_rate_id=standard_vat.id if standard_vat else None,
                vat_rate=standard_vat.rate if standard_vat else 24,
                status='makstud'
            )
            
            db.session.add(invoice1)
            db.session.add(invoice2)
            db.session.flush()
            
            # Create sample invoice lines
            line1 = InvoiceLine(
                invoice_id=invoice1.id,
                description='Web development services',
                qty=1,
                unit_price=344.26,
                line_total=344.26
            )
            line2 = InvoiceLine(
                invoice_id=invoice2.id,
                description='Consulting services',
                qty=8,
                unit_price=131.15,
                line_total=1049.20
            )
            
            db.session.add(line1)
            db.session.add(line2)
            
            # Calculate totals
            invoice1.calculate_totals()
            invoice2.calculate_totals()
            
            db.session.commit()
            click.echo('Sample data created successfully.')
            click.echo(f'Created invoices with VAT rate: {standard_vat.name if standard_vat else "24% (fallback)"}')
    
    @app.cli.command()
    @click.argument('username')
    @click.argument('email')
    @click.password_option()
    def create_user(username, email, password):
        """Create a new user account."""
        with app.app_context():
            from app.models import User
            
            try:
                user = User.create_user(username=username, email=email, password=password, is_admin=False)
                click.echo(f'Kasutaja {user.username} ({user.email}) on edukalt loodud.')
            except ValueError as e:
                click.echo(f'Viga: {str(e)}', err=True)
            except Exception as e:
                click.echo(f'Viga kasutaja loomisel: {str(e)}', err=True)
    
    @app.cli.command()
    @click.argument('username')
    @click.argument('email')
    @click.password_option()
    def create_admin(username, email, password):
        """Create an admin user account."""
        with app.app_context():
            from app.models import User
            
            try:
                user = User.create_user(username=username, email=email, password=password, is_admin=True)
                click.echo(f'Administraator {user.username} ({user.email}) on edukalt loodud.')
            except ValueError as e:
                click.echo(f'Viga: {str(e)}', err=True)
            except Exception as e:
                click.echo(f'Viga administraatori loomisel: {str(e)}', err=True)
    
    @app.cli.command()
    def list_users():
        """List all users."""
        with app.app_context():
            from app.models import User
            
            users = User.query.order_by(User.created_at.desc()).all()
            if not users:
                click.echo('Kasutajaid pole veel registreeritud.')
                return
            
            click.echo('\nRegistreeritud kasutajad:')
            click.echo('-' * 60)
            for user in users:
                status = 'Aktiivne' if user.is_active else 'Mitteaktiivne'
                role = 'Admin' if user.is_admin else 'Kasutaja'
                click.echo(f'{user.username:20} | {user.email:30} | {role:8} | {status}')
    
    @app.cli.command()
    @click.argument('username')
    def deactivate_user(username):
        """Deactivate a user account."""
        with app.app_context():
            from app.models import User
            
            user = User.get_by_username(username)
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            if not user.is_active:
                click.echo(f'Kasutaja "{username}" on juba deaktiveeritud.')
                return
            
            # Check if this is the last admin
            if user.is_admin:
                active_admins = User.query.filter_by(is_admin=True, is_active=True).count()
                if active_admins <= 1:
                    click.echo('Viimast administraatorit ei saa deaktiveerida.', err=True)
                    return
            
            user.deactivate()
            click.echo(f'Kasutaja "{username}" on deaktiveeritud.')
    
    @app.cli.command()
    @click.argument('username')
    def activate_user(username):
        """Activate a user account."""
        with app.app_context():
            from app.models import User
            
            user = User.query.filter_by(username=username).first()
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            if user.is_active:
                click.echo(f'Kasutaja "{username}" on juba aktiivne.')
                return
            
            user.activate()
            click.echo(f'Kasutaja "{username}" on aktiveeritud.')
    
    @app.cli.command()
    @click.argument('username')
    @click.password_option()
    def reset_password(username, password):
        """Reset user password."""
        with app.app_context():
            from app.models import User
            
            user = User.get_by_username(username)
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            user.set_password(password)
            db.session.commit()
            click.echo(f'Kasutaja "{username}" parool on lähtestatud.')
    
    @app.cli.command()
    @click.argument('username')
    def delete_user(username):
        """Delete a user account."""
        with app.app_context():
            from app.models import User
            
            user = User.query.filter_by(username=username).first()
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            # Prevent deleting the last admin
            if user.is_admin:
                admin_count = User.query.filter_by(is_admin=True).count()
                if admin_count <= 1:
                    click.echo('Viga: Ei saa kustutada viimast administraatorit.', err=True)
                    return
            
            # Delete the user
            db.session.delete(user)
            db.session.commit()
            click.echo(f'Kasutaja "{username}" on kustutatud.')
    
    @app.cli.command()
    @click.argument('username')
    def make_admin(username):
        """Grant admin privileges to a user."""
        with app.app_context():
            from app.models import User
            
            user = User.get_by_username(username)
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            if user.is_admin:
                click.echo(f'Kasutaja "{username}" on juba administraator.')
                return
            
            user.is_admin = True
            db.session.commit()
            click.echo(f'Kasutaja "{username}" on nüüd administraator.')
    
    @app.cli.command()
    @click.argument('username')
    def revoke_admin(username):
        """Revoke admin privileges from a user."""
        with app.app_context():
            from app.models import User
            
            user = User.get_by_username(username)
            if not user:
                click.echo(f'Kasutajat "{username}" ei leitud.', err=True)
                return
            
            if not user.is_admin:
                click.echo(f'Kasutaja "{username}" ei ole administraator.')
                return
            
            # Check if this is the last admin
            active_admins = User.query.filter_by(is_admin=True, is_active=True).count()
            if active_admins <= 1:
                click.echo('Viimaselt administraatorilt ei saa õigusi ära võtta.', err=True)
                return
            
            user.is_admin = False
            db.session.commit()
            click.echo(f'Kasutaja "{username}" ei ole enam administraator.')
    
    @app.cli.command()
    def init_vat_rates():
        """Initialize default Estonian VAT rates."""
        with app.app_context():
            from app.models import VatRate
            
            try:
                VatRate.create_default_rates()
                click.echo('Default Estonian VAT rates created successfully:')
                
                # Display created rates
                rates = VatRate.get_active_rates()
                for rate in rates:
                    click.echo(f'  • {rate.name}: {rate.rate}% - {rate.description}')
                
            except Exception as e:
                click.echo(f'Error creating VAT rates: {str(e)}')
                return
    
    @app.cli.command()
    def update_overdue():
        """Update overdue invoice statuses."""
        with app.app_context():
            from app.models import Invoice
            
            try:
                updated_count = Invoice.update_overdue_invoices()
                if updated_count > 0:
                    db.session.commit()
                    click.echo(f'Updated {updated_count} invoices to overdue status.')
                else:
                    click.echo('No invoices found that need overdue status update.')
                    
            except Exception as e:
                db.session.rollback()
                click.echo(f'Error updating overdue invoices: {str(e)}')
    
    @app.cli.command()
    def migrate_statuses():
        """Migrate old invoice statuses to new 2-status system."""
        with app.app_context():
            from app.models import Invoice
            
            try:
                updated_count = Invoice.migrate_old_statuses()
                if updated_count > 0:
                    db.session.commit()
                    click.echo(f'Successfully migrated {updated_count} invoice statuses to new system.')
                    click.echo('Old statuses → New statuses:')
                    click.echo('  mustand → maksmata')
                    click.echo('  saadetud → maksmata') 
                    click.echo('  tähtaeg ületatud → maksmata')
                    click.echo('  makstud → makstud (unchanged)')
                else:
                    click.echo('No invoice statuses needed migration.')
                    
            except Exception as e:
                db.session.rollback()
                click.echo(f'Error migrating statuses: {str(e)}')
    
    @app.cli.command()
    @click.option('--days', default=30, help='Clean attempts older than this many days')
    def cleanup_login_attempts(days):
        """Clean up old login attempts."""
        with app.app_context():
            from app.models import LoginAttempt
            
            try:
                deleted_count = LoginAttempt.cleanup_old_attempts(days=days)
                click.echo(f'Cleaned up {deleted_count} login attempts older than {days} days.')
            except Exception as e:
                click.echo(f'Error cleaning up login attempts: {str(e)}')
    
    return app