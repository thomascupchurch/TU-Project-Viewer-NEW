import time, secrets, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import UserDB, db

auth_bp = Blueprint('auth', __name__)

FAILED_LOGINS = {}
LOGIN_RATE_LIMIT_WINDOW = 600
LOGIN_RATE_LIMIT_MAX = 5
RESET_EXPIRY_SECONDS = 3600

def _login_rate_limited(key):
    now = time.time()
    attempts = [t for t in FAILED_LOGINS.get(key, []) if now - t < LOGIN_RATE_LIMIT_WINDOW]
    FAILED_LOGINS[key] = attempts
    if len(attempts) >= LOGIN_RATE_LIMIT_MAX:
        return True, int(LOGIN_RATE_LIMIT_WINDOW - (now - attempts[0]))
    return False, 0

def _record_failed_login(key):
    FAILED_LOGINS.setdefault(key, []).append(time.time())

def password_errors(pw: str):
    req = []
    if len(pw) < 8: req.append('8+ chars')
    if not any(c.islower() for c in pw): req.append('lowercase')
    if not any(c.isupper() for c in pw): req.append('uppercase')
    if not any(c.isdigit() for c in pw): req.append('digit')
    if not any(c in '!@#$%^&*()_+-=' for c in pw): req.append('symbol')
    return req

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    users = _load_users()
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        if not username or not password:
            flash('Username and password are required.')
            return render_template('register.html')
        perrs = password_errors(password)
        if perrs:
            flash('Password must contain: ' + ', '.join(perrs))
            return render_template('register.html')
        if any(u['username'].lower() == username.lower() for u in users):
            flash('Username already exists.')
            return render_template('register.html')
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        users.append({'id': user_id, 'username': username, 'password_hash': password_hash, 'is_admin': False})
        _save_users(users)
        flash('Registration successful. Please log in.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    users = _load_users()
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        key = (request.remote_addr or 'unknown') + '|' + username.lower()
        limited, wait = _login_rate_limited(key)
        if limited:
            flash(f'Too many login attempts. Try again in ~{wait} seconds.')
            return render_template('login.html')
        user = next((u for u in users if u['username'].lower() == username.lower()), None)
        if user and password and check_password_hash(user['password_hash'], password):
            FAILED_LOGINS.pop(key, None)
            login_user(_make_user(user))
            return redirect(url_for('tasks_page'))
        _record_failed_login(key)
        flash('Invalid username or password.')
    return render_template('login.html')

def _make_user(u):
    from flask_login import UserMixin
    class _U(UserMixin):
        pass
    x = _U(); x.id = u['id']; x.username = u['username']; x.password_hash = u['password_hash']; x.is_admin = u.get('is_admin', False); return x

def _load_users():
    # Users are stored in DB via UserDB; provide simple list structure for legacy compatibility
    return [ {'id': u.id, 'username': u.username, 'password_hash': u.password_hash, 'is_admin': u.is_admin } for u in UserDB.query.all() ]

def _save_users(users_list):
    existing = {u.id: u for u in UserDB.query.all()}
    changed = False
    for u in users_list:
        if u['id'] not in existing:
            db.session.add(UserDB(id=u['id'], username=u['username'], password_hash=u['password_hash'], is_admin=u.get('is_admin', False)))
            changed = True
    if changed:
        db.session.commit()

def _find_user_by_reset_token(token):
    for u in UserDB.query.all():
        if u.reset_token == token:
            return u
    return None

@auth_bp.route('/forgot', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        if username:
            u = UserDB.query.filter(UserDB.username.ilike(username)).first()
            if u:
                u.reset_token = secrets.token_urlsafe(32)
                u.reset_expires = time.time() + RESET_EXPIRY_SECONDS
                db.session.commit()
                flash('If the account exists, a reset token was generated.')
            else:
                flash('If the account exists, a reset token was generated.')
            return render_template('forgot_password.html', token_display=getattr(u,'reset_token', None), expires_minutes=RESET_EXPIRY_SECONDS//60)
    return render_template('forgot_password.html', token_display=None)

@auth_bp.route('/reset/<token>', methods=['GET','POST'])
def reset_password(token):
    u = _find_user_by_reset_token(token)
    if not u or u.reset_expires < time.time():
        flash('Invalid or expired reset token.')
        return render_template('reset_password.html', invalid=True)
    if request.method == 'POST':
        pw1 = request.form.get('password','')
        pw2 = request.form.get('confirm_password','')
        if pw1 != pw2:
            flash('Passwords do not match.')
            return render_template('reset_password.html', token=token, invalid=False)
        errs = password_errors(pw1)
        if errs:
            flash('Password must contain: ' + ', '.join(errs))
            return render_template('reset_password.html', token=token, invalid=False)
        u.password_hash = generate_password_hash(pw1)
        u.reset_token = None; u.reset_expires = None
        db.session.commit()
        flash('Password reset successful. Please log in.')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token, invalid=False)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user(); flash('Logged out.'); return redirect(url_for('auth.login'))