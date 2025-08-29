from flask import Blueprint, render_template, flash, redirect, url_for, request, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, LoginAttempt
from app.forms import LoginForm, RegistrationForm, ChangePasswordForm, UserProfileForm
from app.logging_config import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# API endpoints are exempt from CSRF via Flask-WTF configuration

# Rate limiting decorator for manual application
def get_limiter():
    """Get limiter instance from current app."""
    return current_app.extensions.get('limiter')

def check_rate_limit(ip_address, max_attempts=5, window_minutes=15):
    """Check if IP address has exceeded rate limit."""
    recent_failures = LoginAttempt.get_recent_failures(ip_address, window_minutes)
    return recent_failures >= max_attempts

def log_login_attempt(username, success=False):
    """Log login attempt with IP and user agent."""
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    user_agent = request.environ.get('HTTP_USER_AGENT', '')
    
    LoginAttempt.log_attempt(
        ip_address=ip_address,
        username=username,
        success=success,
        user_agent=user_agent
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Enhanced user login route with rate limiting and security monitoring."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.overview'))
    
    # Check rate limiting
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    if check_rate_limit(ip_address):
        logger.warning(f'Rate limit exceeded for IP: {ip_address}')
        flash('Liiga palju sisselogimiskatseid. Palun proovi hiljem uuesti.', 'danger')
        return render_template('auth/login.html', form=LoginForm()), 429
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        
        if form.validate_login():
            user = form.user
            
            # Log successful attempt
            log_login_attempt(username, success=True)
            
            # Login user with enhanced session settings
            remember_duration = timedelta(days=30) if form.remember_me.data else None
            login_user(user, remember=form.remember_me.data, duration=remember_duration)
            user.update_last_login()
            
            logger.info(f'User {user.username} logged in successfully from IP: {ip_address}')
            flash(f'Tere tulemast, {user.username}!', 'success')
            
            # Redirect to next page or overview
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard.overview')
            return redirect(next_page)
        else:
            # Log failed attempt
            log_login_attempt(username, success=False)
            logger.warning(f'Failed login attempt for user: {username} from IP: {ip_address}')
            flash('Vigane kasutajanimi või parool.', 'danger')
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # Only admin can access registration
    if not current_user.is_admin:
        flash('Sul pole õigust uue kasutaja loomiseks.', 'danger')
        return redirect(url_for('dashboard.overview'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Check if this is the first user (make them admin)
            is_first_user = User.query.count() == 0
            
            user = User.create_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
                is_admin=is_first_user
            )
            
            logger.info(f'New user registered: {user.username} ({"admin" if is_first_user else "user"})')
            flash(f'Registreerimine õnnestus! {"Sa oled administraator." if is_first_user else ""}', 'success')
            return redirect(url_for('auth.login'))
            
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            logger.error(f'Registration error for {form.username.data}: {str(e)}')
            flash('Registreerimisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Enhanced user logout route with secure session cleanup."""
    username = current_user.username
    
    # Clear all session data for security
    session.clear()
    
    # Logout user
    logout_user()
    
    logger.info(f'User {username} logged out successfully')
    flash('Oled edukalt välja logitud.', 'info')
    
    # Redirect to login with cache-busting headers
    response = redirect(url_for('auth.login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management route."""
    form = UserProfileForm(current_user)
    
    if form.validate_on_submit():
        try:
            current_user.username = form.username.data
            current_user.email = form.email.data
            db.session.commit()
            
            logger.info(f'User profile updated: {current_user.username}')
            flash('Profiil on edukalt uuendatud.', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Profile update error for {current_user.username}: {str(e)}')
            flash('Profiili uuendamisel tekkis viga.', 'danger')
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    return render_template('auth/profile.html', form=form)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password route."""
    form = ChangePasswordForm(current_user)
    
    if form.validate_on_submit():
        try:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            logger.info(f'Password changed for user: {current_user.username}')
            flash('Parool on edukalt muudetud.', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Password change error for {current_user.username}: {str(e)}')
            flash('Parooli muutmisel tekkis viga.', 'danger')
    
    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/users')
@login_required
def users():
    """User management route (admin only)."""
    if not current_user.is_admin:
        flash('Sul puudub õigus sellele lehele.', 'danger')
        return redirect(url_for('dashboard.overview'))
    
    users = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).all()
    return render_template('auth/users.html', users=users)


@auth_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def toggle_admin(user_id):
    """Toggle admin status of a user."""
    if not current_user.is_admin:
        flash('Sul puudub õigus sellele toimingule.', 'danger')
        return redirect(url_for('dashboard.overview'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent removing admin rights from the last admin
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True, is_active=True).count()
        if admin_count <= 1:
            flash('Viimaselt administraatorilt ei saa õigusi ära võtta.', 'danger')
            return redirect(url_for('auth.users'))
    
    try:
        user.is_admin = not user.is_admin
        db.session.commit()
        
        status = 'administraator' if user.is_admin else 'kasutaja'
        logger.info(f'User {user.username} role changed to {status} by {current_user.username}')
        flash(f'Kasutaja {user.username} on nüüd {status}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error changing admin status for {user.username}: {str(e)}')
        flash('Õiguste muutmisel tekkis viga.', 'danger')
    
    return redirect(url_for('auth.users'))


@auth_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
def deactivate_user(user_id):
    """Deactivate a user account."""
    if not current_user.is_admin:
        flash('Sul puudub õigus sellele toimingule.', 'danger')
        return redirect(url_for('dashboard.overview'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent deactivating yourself
    if user.id == current_user.id:
        flash('Sa ei saa enda kontot deaktiveerida.', 'danger')
        return redirect(url_for('auth.users'))
    
    # Prevent deactivating the last admin
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True, is_active=True).count()
        if admin_count <= 1:
            flash('Viimast administraatorit ei saa deaktiveerida.', 'danger')
            return redirect(url_for('auth.users'))
    
    try:
        user.deactivate()
        logger.info(f'User {user.username} deactivated by {current_user.username}')
        flash(f'Kasutaja {user.username} konto on deaktiveeritud.', 'success')
        
    except Exception as e:
        logger.error(f'Error deactivating user {user.username}: {str(e)}')
        flash('Kasutaja deaktiveerimisel tekkis viga.', 'danger')
    
    return redirect(url_for('auth.users'))


# JSON API Endpoints for Modern Frontend Integration

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """JSON API endpoint for login."""
    if current_user.is_authenticated:
        return jsonify({
            'success': False,
            'message': 'Oled juba sisse logitud.',
            'redirect': url_for('dashboard.overview')
        }), 400
    
    # Check rate limiting
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    if check_rate_limit(ip_address):
        logger.warning(f'API rate limit exceeded for IP: {ip_address}')
        return jsonify({
            'success': False,
            'message': 'Liiga palju sisselogimiskatseid. Palun proovi hiljem uuesti.',
            'retry_after': 900  # 15 minutes in seconds
        }), 429
    
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Puuduvad andmed.'
        }), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    remember_me = data.get('remember_me', False)
    
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Kasutajanimi ja parool on kohustuslikud.',
            'errors': {
                'username': ['Kasutajanimi on kohustuslik'] if not username else [],
                'password': ['Parool on kohustuslik'] if not password else []
            }
        }), 400
    
    # Validate user credentials
    user = User.get_by_username(username)
    if not user or not user.check_password(password):
        # Log failed attempt
        log_login_attempt(username, success=False)
        logger.warning(f'API failed login attempt for user: {username} from IP: {ip_address}')
        
        return jsonify({
            'success': False,
            'message': 'Vigane kasutajanimi või parool.'
        }), 401
    
    # Successful login
    log_login_attempt(username, success=True)
    
    # Login user
    remember_duration = timedelta(days=30) if remember_me else None
    login_user(user, remember=remember_me, duration=remember_duration)
    user.update_last_login()
    
    logger.info(f'API user {user.username} logged in successfully from IP: {ip_address}')
    
    return jsonify({
        'success': True,
        'message': f'Tere tulemast, {user.username}!',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'last_login': user.last_login.isoformat() if user.last_login else None
        },
        'redirect': url_for('dashboard.overview')
    }), 200


@auth_bp.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """JSON API endpoint for logout."""
    username = current_user.username
    
    # Clear session data
    session.clear()
    
    # Logout user
    logout_user()
    
    logger.info(f'API user {username} logged out')
    
    return jsonify({
        'success': True,
        'message': 'Oled edukalt välja logitud.',
        'redirect': url_for('auth.login')
    }), 200


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """JSON API endpoint for registration."""
    if current_user.is_authenticated:
        return jsonify({
            'success': False,
            'message': 'Oled juba sisse logitud.',
            'redirect': url_for('dashboard.overview')
        }), 400
    
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Puuduvad andmed.'
        }), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    password2 = data.get('password2', '')
    
    # Validation
    errors = {}
    
    if not username:
        errors['username'] = ['Kasutajanimi on kohustuslik']
    elif len(username) < 3 or len(username) > 80:
        errors['username'] = ['Kasutajanimi peab olema 3-80 tähemärki']
    
    if not email:
        errors['email'] = ['E-posti aadress on kohustuslik']
    elif '@' not in email:
        errors['email'] = ['Vigane e-posti aadress']
    
    if not password:
        errors['password'] = ['Parool on kohustuslik']
    elif len(password) < 8:
        errors['password'] = ['Parool peab olema vähemalt 8 tähemärki']
    
    if password != password2:
        errors['password2'] = ['Paroolid ei kattu']
    
    # Check for existing users
    if username and User.query.filter_by(username=username).first():
        errors['username'] = [f'Kasutajanimi "{username}" on juba kasutusel']
    
    if email and User.query.filter_by(email=email).first():
        errors['email'] = [f'E-posti aadress "{email}" on juba kasutusel']
    
    if errors:
        return jsonify({
            'success': False,
            'message': 'Sisestatud andmetes on vigu.',
            'errors': errors
        }), 400
    
    try:
        # Check if this is the first user (make them admin)
        is_first_user = User.query.count() == 0
        
        user = User.create_user(
            username=username,
            email=email,
            password=password,
            is_admin=is_first_user
        )
        
        logger.info(f'API new user registered: {user.username} ({"admin" if is_first_user else "user"})')
        
        return jsonify({
            'success': True,
            'message': f'Registreerimine õnnestus! {"Sa oled administraator." if is_first_user else ""}',
            'redirect': url_for('auth.login')
        }), 201
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f'API registration error for {username}: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Registreerimisel tekkis viga. Palun proovi uuesti.'
        }), 500


@auth_bp.route('/api/session', methods=['GET'])
def api_session():
    """Get current session information."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'is_admin': current_user.is_admin,
                'last_login': current_user.last_login.isoformat() if current_user.last_login else None
            }
        }), 200
    else:
        return jsonify({
            'authenticated': False,
            'user': None
        }), 200


@auth_bp.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    """JSON API endpoint for changing password."""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Puuduvad andmed.'
        }), 400
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    new_password2 = data.get('new_password2', '')
    
    # Validation
    errors = {}
    
    if not current_password:
        errors['current_password'] = ['Praegune parool on kohustuslik']
    elif not current_user.check_password(current_password):
        errors['current_password'] = ['Praegune parool on vale']
    
    if not new_password:
        errors['new_password'] = ['Uus parool on kohustuslik']
    elif len(new_password) < 8:
        errors['new_password'] = ['Parool peab olema vähemalt 8 tähemärki']
    
    if new_password != new_password2:
        errors['new_password2'] = ['Paroolid ei kattu']
    
    if errors:
        return jsonify({
            'success': False,
            'message': 'Sisestatud andmetes on vigu.',
            'errors': errors
        }), 400
    
    try:
        current_user.set_password(new_password)
        db.session.commit()
        
        logger.info(f'API password changed for user: {current_user.username}')
        
        return jsonify({
            'success': True,
            'message': 'Parool on edukalt muudetud.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'API password change error for {current_user.username}: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Parooli muutmisel tekkis viga.'
        }), 500