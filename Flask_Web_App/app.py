"""Flask application main module (repaired header)."""

# --- Proper Imports & Initialization (reconstructed after corruption) ---
import os, io, json, csv, time, uuid, secrets, zipfile, re
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify,
    send_file, send_from_directory, make_response, abort, Response, flash
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import matplotlib
matplotlib.use('Agg')  # headless environments
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from resources_bp import resources_bp
from auth_bp import auth_bp

from db import (
    db, UserDB, PhaseDB, ItemDB, TaskDB, SettingDB, ContactDB, AssetDB,
    ensure_admin_user, migrate_tasks_to_items
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash, is_admin=False):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):  # pragma: no cover - simple loader
    with app.app_context():
        u = UserDB.query.get(user_id)
        if u:
            return User(u.id, u.username, u.password_hash, u.is_admin)
        return None

with app.app_context():
    db.create_all()
    try:
        migrate_tasks_to_items(db.session)
        ensure_admin_user(db.session)
    except Exception as e:  # pragma: no cover
        print('[WARN] Initialization issue:', e)

# In-memory caches (populated by loaders defined later in file)
users = []
tasks = []
phases = []
settings = {}

# Register resources blueprint
app.register_blueprint(resources_bp)
app.register_blueprint(auth_bp)

# --- Items CRUD Page (clean, relocated) ---
@app.route('/items', methods=['GET', 'POST'])
@login_required
def items_page():
    """Items CRUD page (user-scoped view) with multi-PDF support."""
    load_tasks(); load_phases(); load_settings()
    try:
        pdf_files = [f for f in os.listdir(os.path.join(BASE_DIR, 'static', 'uploads')) if f.lower().endswith('.pdf')]
    except Exception:
        pdf_files = []
    user_tasks = [t for t in tasks if t.get('user_id') == current_user.get_id() or current_user.get_id() in t.get('shared_with', [])]
    alert_message = None
    if request.method == 'POST':
        form = request.form
        name = form.get('name', '').strip()
        phase = form.get('phase', '').strip()
        start = form.get('start', '').strip()
        responsible = form.get('responsible', '').strip()
        duration = form.get('duration', '').strip()
        percent_complete = form.get('percent_complete', '0').strip()
        status = form.get('status', '').strip() or 'Not Started'
        milestone = form.get('milestone', '').strip()
        parent = form.get('parent', '').strip()
        depends_on = form.get('depends_on', '').strip()
        resources = form.get('resources', '').strip()
        notes = form.get('notes', '').strip()
        pdf_page = form.get('pdf_page', '').strip()
        pdf_file = form.get('pdf_file', '').strip()
        document_links_raw = form.get('document_links', '').strip()
        links_list = [l.strip() for l in document_links_raw.split(',') if l.strip()]
        share_with_raw = form.get('share_with', '').strip()
        share_with_ids = []
        if share_with_raw:
            load_users()
            for uname in [u.strip() for u in share_with_raw.split(',') if u.strip()]:
                urec = next((u for u in users if u['username'] == uname), None)
                if urec:
                    share_with_ids.append(urec['id'])
        external_flag = form.get('external_item') or form.get('external_task')
        external_item_flag = True if external_flag == 'on' else False
        external_milestone = True if form.get('external_milestone') == 'on' else False
        edit_idx = form.get('edit_idx', '').strip()
        # Attachments
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        attachment_filenames = []
        if 'attachments' in request.files:
            for attachment in request.files.getlist('attachments'):
                if attachment and attachment.filename:
                    safe_name = attachment.filename.replace('..', '').replace('/', '_').replace('\\', '_')
                    attachment.save(os.path.join(UPLOAD_FOLDER, safe_name))
                    attachment_filenames.append(safe_name)
        # Dependency enforcement
        if depends_on:
            dep_task = next((t for t in tasks if t['name'] == depends_on and t.get('user_id') == current_user.get_id()), None)
            if dep_task and dep_task.get('start') and dep_task.get('duration'):
                try:
                    dep_start = datetime.strptime(dep_task['start'], '%Y-%m-%d')
                    dep_duration = int(dep_task.get('duration', 1) or 1)
                    dep_end_date = dep_start + timedelta(days=dep_duration)
                    if start:
                        this_start = datetime.strptime(start, '%Y-%m-%d')
                        if this_start < dep_end_date:
                            alert_message = f"Task '{name}' cannot start before its dependency '{depends_on}' is complete (>= {dep_end_date.strftime('%Y-%m-%d')})."
                except Exception:
                    pass
        if alert_message:
            return render_template('items.html', tasks=user_tasks, alert_message=alert_message, phases=phases, pdf_files=pdf_files)
        # Edit
        if edit_idx.isdigit() and int(edit_idx) < len(tasks):
            task = tasks[int(edit_idx)]
            if not can_edit():
                flash('Editing is restricted to admins.')
                return redirect(url_for('items_page'))
            if task.get('user_id') != current_user.get_id() and not getattr(current_user, 'is_admin', False):
                flash('You can only edit your own tasks.')
                return redirect(url_for('items_page'))
            with app.app_context():
                rec = ItemDB.query.get(task['id'])
                if rec:
                    rec.name = name
                    rec.phase = phase
                    rec.start = start
                    rec.responsible = responsible
                    rec.duration = duration
                    rec.percent_complete = percent_complete
                    rec.status = status
                    rec.milestone = milestone
                    rec.parent = parent
                    rec.depends_on = depends_on
                    rec.resources = resources
                    rec.notes = notes
                    rec.pdf_page = pdf_page
                    if pdf_file:
                        rec.pdf_file = pdf_file
                    rec.document_links = ','.join(links_list)
                    rec.external_item = external_item_flag
                    rec.external_milestone = external_milestone
                    rec.shared_with = ','.join(share_with_ids)
                    # merge attachments
                    existing_att = [a for a in (rec.attachments.split(',') if rec.attachments else []) if a]
                    for a in attachment_filenames:
                        if a not in existing_att:
                            existing_att.append(a)
                    rec.attachments = ','.join(existing_att)
                    db.session.commit()
            load_tasks()
            return redirect(url_for('items_page'))
        # Create
        if not can_edit():
            flash('Editing is restricted to admins.')
            return redirect(url_for('items_page'))
        if name:
            with app.app_context():
                rec = ItemDB(
                    user_id=current_user.get_id(),
                    name=name,
                    phase=phase,
                    start=start,
                    responsible=responsible,
                    status=status,
                    percent_complete=percent_complete or 0,
                    attachments=','.join(attachment_filenames),
                    notes=notes,
                    milestone=milestone,
                    duration=duration or 1,
                    parent=parent,
                    depends_on=depends_on,
                    resources=resources,
                    pdf_page=pdf_page,
                    pdf_file=pdf_file or None,
                    document_links=','.join(links_list),
                    external_item=external_item_flag,
                    external_milestone=external_milestone,
                    shared_with=','.join(share_with_ids)
                )
                db.session.add(rec)
                db.session.commit()
            load_tasks()
        return redirect(url_for('items_page'))
    return render_template('items.html', tasks=user_tasks, alert_message=alert_message, phases=phases, pdf_files=pdf_files)

# Re-define register route (was earlier in file) if corrupted by edits
@app.route('/register', methods=['GET', 'POST'])
def register():
    load_users()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
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
        save_users()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')
# --- Admin-only decorator ---
from functools import wraps
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        user = next((u for u in users if str(u['id']) == str(current_user.get_id())), None)
        if not user or not user.get('is_admin', False):
            flash('Admin access required.')
            return redirect(url_for('tasks_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin dashboard ---
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    load_users()
    load_tasks()
    return render_template('admin.html', users=users, tasks=tasks)

# --- Promote user to admin ---
@app.route('/admin/promote/<user_id>')
@login_required
@admin_required
def promote_user(user_id):
    load_users()
    for u in users:
        if str(u['id']) == str(user_id):
            u['is_admin'] = True
            save_users()
            flash(f"User {u['username']} promoted to admin.")
            break
    return redirect(url_for('admin_dashboard'))

# --- Delete user ---
@app.route('/admin/delete_user/<user_id>')
@login_required
@admin_required
def delete_user(user_id):
    load_users()
    global users
    users = [u for u in users if str(u['id']) != str(user_id)]
    save_users()
    flash('User deleted.')
    return redirect(url_for('admin_dashboard'))

FAILED_LOGINS = {}
LOGIN_RATE_LIMIT_WINDOW = 600  # seconds
LOGIN_RATE_LIMIT_MAX = 5

def _login_rate_limited(key):
    now = time.time()
    attempts = [t for t in FAILED_LOGINS.get(key, []) if now - t < LOGIN_RATE_LIMIT_WINDOW]
    FAILED_LOGINS[key] = attempts
    if len(attempts) >= LOGIN_RATE_LIMIT_MAX:
        return True, int(LOGIN_RATE_LIMIT_WINDOW - (now - attempts[0]))
    return False, 0

def _record_failed_login(key):
    FAILED_LOGINS.setdefault(key, []).append(time.time())

@app.route('/login', methods=['GET', 'POST'])
def login():
    load_users()
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
            # On success clear attempts
            FAILED_LOGINS.pop(key, None)
            login_user(User(user['id'], user['username'], user['password_hash'], user.get('is_admin', False)))
            return redirect(url_for('tasks_page'))
        _record_failed_login(key)
        flash('Invalid username or password.')
    return render_template('login.html')

# ---------------- Password Reset (Self-Service Token) ---------------- #
RESET_EXPIRY_SECONDS = 3600  # 1 hour

def _find_user_by_reset_token(token):
    for u in users:
        if u.get('reset_token') == token:
            return u
    return None

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    load_users()
    token_display = None
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        if not username:
            flash('Username required.')
            return render_template('forgot_password.html', token_display=None)
        user = next((u for u in users if u['username'].lower() == username.lower()), None)
        # Always respond generically to prevent user enumeration
        if user:
            user['reset_token'] = secrets.token_urlsafe(32)
            user['reset_expires'] = time.time() + RESET_EXPIRY_SECONDS
            save_users()
            token_display = user['reset_token']  # Since no email system, show token for manual use
            flash('If the account exists, a reset token was generated.')
        else:
            flash('If the account exists, a reset token was generated.')
        return render_template('forgot_password.html', token_display=token_display, expires_minutes=RESET_EXPIRY_SECONDS//60)
    return render_template('forgot_password.html', token_display=None)

@app.route('/reset/<token>', methods=['GET','POST'])
def reset_password(token):
    load_users()
    user = _find_user_by_reset_token(token)
    if not user or user.get('reset_expires',0) < time.time():
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
        user['password_hash'] = generate_password_hash(pw1)
        # Invalidate token
        user.pop('reset_token', None)
        user.pop('reset_expires', None)
        save_users()
        flash('Password reset successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token, invalid=False)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('login'))

PHASES_FILE = None  # legacy removed
phases = []

def load_phases():
    global phases
    try:
        with app.app_context():
            db_phases = PhaseDB.query.order_by(PhaseDB.id.asc()).all()
            phases = [{'id': p.id, 'name': p.name} for p in db_phases]
    except Exception as e:
        print('[ERROR] load_phases DB:', e)

def save_phases():
    # Persist in-memory phases list back to DB (used after modifications)
    try:
        with app.app_context():
            existing = {p.id: p for p in PhaseDB.query.all()}
            # Upsert existing by id; new phases without id handled earlier.
            for p in phases:
                if 'id' in p and p['id'] in existing:
                    existing[p['id']].name = p['name']
            db.session.commit()
    except Exception as e:
        print('[ERROR] save_phases DB:', e)

@app.route('/create_phase', methods=['POST'])
@login_required
def create_phase():
    """Create a phase (global). Accepts JSON: {"name": "Phase Name"}."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400
    with app.app_context():
        if PhaseDB.query.filter(db.func.lower(PhaseDB.name) == name.lower()).first():
            return jsonify({'success': False, 'error': 'Phase already exists'}), 409
        phase = PhaseDB(name=name)
        db.session.add(phase)
        db.session.commit()
        return jsonify({'success': True, 'phase': {'id': phase.id, 'name': phase.name}})

# --- Phase creation ---
@app.route('/phases', methods=['GET', 'POST'])
@login_required
def phases_page():
    if request.method == 'POST':
        phase_name = request.form.get('phase_name', '').strip()
        if phase_name:
            with app.app_context():
                if not PhaseDB.query.filter(db.func.lower(PhaseDB.name) == phase_name.lower()).first():
                    db.session.add(PhaseDB(name=phase_name))
                    db.session.commit()
    with app.app_context():
        db_phases = PhaseDB.query.order_by(PhaseDB.id.asc()).all()
        return render_template('phases.html', phases=[{'id': p.id, 'name': p.name} for p in db_phases])

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks_page():
    # Backward compatibility redirect
    if request.method == 'POST':
        # process via items_page
        return items_page()
    return redirect(url_for('items_page'), code=301)

# --- One-time migration route (admin only) ---
@app.route('/migrate_legacy_json')
@login_required
def migrate_legacy_json():
    if not getattr(current_user, 'is_admin', False):
        abort(403)
    imported = {'users': 0, 'phases': 0, 'tasks': 0, 'settings': 0}
    # Users (skip – already migrated by load/save users logic)
    # Phases
    if os.path.exists(PHASES_FILE):
        with open(PHASES_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
        with app.app_context():
            for p in data:
                if not PhaseDB.query.filter_by(name=p.get('name')).first():
                    db.session.add(PhaseDB(name=p.get('name')))
                    imported['phases'] += 1
            db.session.commit()
    # Tasks
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
        with app.app_context():
            for t in data:
                if not t.get('name'):
                    continue
                if not TaskDB.query.filter_by(name=t.get('name')).first():
                    db.session.add(TaskDB(
                        user_id=t.get('user_id'),
                        name=t.get('name'),
                        phase=t.get('phase'),
                        start=t.get('start'),
                        duration=t.get('duration'),
                        responsible=t.get('responsible'),
                        status=t.get('status'),
                        percent_complete=t.get('percent_complete'),
                        milestone=t.get('milestone'),
                        parent=t.get('parent'),
                        depends_on=t.get('depends_on'),
                        resources=t.get('resources'),
                        notes=t.get('notes'),
                        pdf_page=t.get('pdf_page'),
                        external_task=t.get('external_task', False),
                        external_milestone=t.get('external_milestone', False),
                        document_links=','.join(t.get('document_links', [])) if isinstance(t.get('document_links'), list) else (t.get('document_links') or ''),
                        attachments=','.join(t.get('attachments', [])) if isinstance(t.get('attachments'), list) else (t.get('attachments') or ''),
                        shared_with=','.join(t.get('shared_with', [])) if isinstance(t.get('shared_with'), list) else (t.get('shared_with') or ''),
                    ))
                    imported['tasks'] += 1
            db.session.commit()
    # Settings
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
        if isinstance(data, dict):
            with app.app_context():
                for k,v in data.items():
                    if not SettingDB.query.get(k):
                        db.session.add(SettingDB(key=k, value=str(v)))
                        imported['settings'] += 1
                db.session.commit()
    load_tasks(); load_phases(); load_settings()
    return jsonify({'success': True, 'imported': imported})

# --- iCalendar Export Route ---
@app.route('/calendar_export_ics')
def calendar_export_ics():
    load_tasks()
    ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TU Project Viewer//EN',
        'CALSCALE:GREGORIAN'
    ]
    for t in tasks:
        if not t.get('start'):
            continue
        dt = t['start']
        # Try to format as YYYYMMDD or YYYYMMDDTHHMMSSZ
        dt_fmt = dt.replace('-', '').replace(':', '').replace(' ', 'T')
        ics.append('BEGIN:VEVENT')
        ics.append(f'SUMMARY:{t.get("name", "Task")}')
        ics.append(f'DTSTART;VALUE=DATE:{dt_fmt}')
        if t.get('notes'):
            ics.append(f'DESCRIPTION:{t["notes"]}')
        ics.append('END:VEVENT')
    ics.append('END:VCALENDAR')
    ics_str = '\r\n'.join(ics)
    return Response(ics_str, mimetype='text/calendar', headers={
        'Content-Disposition': 'attachment; filename=project_tasks.ics'
    })
# --- Project Timeline Helper ---
def get_project_timeline_data(tasks):
    # Extract milestones and phases (tasks with 'milestone' or status 'Completed' or 'In Progress')
    timeline_items = []
    for t in tasks:
        # Treat as milestone if 'milestone' field is set or if marked as milestone in type
        if t.get('milestone') or t.get('status') == 'Completed' or t.get('status') == 'In Progress':
            timeline_items.append({
                'name': t.get('milestone') or t.get('name'),
                'date': t.get('start'),
                'type': 'milestone' if t.get('milestone') else 'phase',
            })
    # Sort by date
    timeline_items = [item for item in timeline_items if item['date']]
    timeline_items.sort(key=lambda x: x['date'])
    return timeline_items


# --- Timeline Route (moved below app creation) ---
@app.route('/timeline')
@login_required
def timeline_page():
    load_tasks()
    timeline_items = get_project_timeline_data(tasks)
    return render_template('timeline.html', tasks=tasks, timeline_items=timeline_items)

@app.route('/control-panel')
@login_required
@admin_required
def control_panel_page():
    load_users()
    # Provide users (excluding password hashes) to template
    safe_users = [
        {
            'id': u['id'],
            'username': u['username'],
            'is_admin': u.get('is_admin', False)
        } for u in users
    ]
    return render_template('control_panel.html', users=safe_users)

@app.route('/settings_json')
@login_required
@admin_required
def settings_json():
    load_settings()
    return jsonify({'open_editing': settings.get('open_editing', False)})

@app.route('/set_open_editing', methods=['POST'])
@login_required
@admin_required
def set_open_editing():
    data = request.get_json(force=True, silent=True) or {}
    val = bool(data.get('open_editing', False))
    load_settings()
    settings['open_editing'] = val
    save_settings()
    return jsonify({'success': True, 'open_editing': settings['open_editing']})

# --- User management API (admin only) ---
@app.route('/admin/users_json')
@login_required
@admin_required
def admin_users_json():
    load_users()
    return jsonify([
        {
            'id': u['id'],
            'username': u['username'],
            'is_admin': u.get('is_admin', False)
        } for u in users
    ])

@app.route('/admin/create_user', methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    load_users()
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    is_admin = bool(data.get('is_admin', False))
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    if any(u['username'].lower() == username.lower() for u in users):
        return jsonify({'success': False, 'error': 'Username already exists'}), 409
    new_user = {
        'id': str(uuid.uuid4()),
        'username': username,
        'password_hash': generate_password_hash(password),
        'is_admin': is_admin
    }
    users.append(new_user)
    save_users()
    return jsonify({'success': True, 'user': {'id': new_user['id'], 'username': new_user['username'], 'is_admin': new_user['is_admin']}})

@app.route('/admin/set_admin', methods=['POST'])
@login_required
@admin_required
def admin_set_admin():
    load_users()
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id')
    is_admin = bool(data.get('is_admin'))
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400
    target = next((u for u in users if str(u['id']) == str(user_id)), None)
    if not target:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    # Prevent demoting last admin
    if not is_admin:
        other_admins = [u for u in users if u.get('is_admin', False) and str(u['id']) != str(user_id)]
        if not other_admins:
            return jsonify({'success': False, 'error': 'Cannot remove the last admin'}), 400
    target['is_admin'] = is_admin
    save_users()
    return jsonify({'success': True})

@app.route('/admin/reset_password', methods=['POST'])
@login_required
@admin_required
def admin_reset_password():
    load_users()
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id')
    new_password = (data.get('new_password') or '').strip()
    if not user_id or not new_password:
        return jsonify({'success': False, 'error': 'user_id and new_password required'}), 400
    target = next((u for u in users if str(u['id']) == str(user_id)), None)
    if not target:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    target['password_hash'] = generate_password_hash(new_password)
    save_users()
    return jsonify({'success': True})

@app.route('/admin/delete_user', methods=['POST'])
@login_required
@admin_required
def admin_delete_user():
    load_users()
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400
    target = next((u for u in users if str(u['id']) == str(user_id)), None)
    if not target:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    # Prevent deleting last admin
    if target.get('is_admin', False):
        other_admins = [u for u in users if u.get('is_admin', False) and str(u['id']) != str(user_id)]
        if not other_admins:
            return jsonify({'success': False, 'error': 'Cannot delete the last admin'}), 400
    # Remove user
    remaining = [u for u in users if str(u['id']) != str(user_id)]
    # Reassign tasks belonging to deleted user? For now just leave tasks with orphaned user_id
    # Could optionally scrub or transfer ownership.
    users.clear()
    users.extend(remaining)
    save_users()
    return jsonify({'success': True})

# --- Calendar View Route ---
@app.route('/calendar')
@login_required
def calendar_view():
    return render_template('calendar.html')

# --- Kanban View Route ---
@app.route('/kanban')
@login_required
def kanban_view():
    return render_template('kanban.html', tasks=tasks)


# --- Tasks JSON for Calendar & API ---
@app.route('/tasks_json')
@login_required
def tasks_json():
    # Return all fields for each task, including id and parent (by id)
    enriched = []
    for t in tasks:
        td = dict(t)
        # ensure pdf_file present even if older cache entries
        if 'pdf_file' not in td:
            td['pdf_file'] = ''
        enriched.append(td)
    return jsonify(enriched)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'  # legacy single-PDF fallback

TASKS_FILE = None  # legacy removed
tasks = []
next_task_id = 1

# --- Delete Task ---
@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json or {}
    task_id = data.get('task_id')
    idx = data.get('task_idx')  # legacy support
    try:
        if task_id is not None:
            task_id = int(task_id)
            with app.app_context():
                t = ItemDB.query.get(task_id)
                if not t:
                    return jsonify({'success': False, 'error': 'Task not found'}), 404
                # remove attachments from disk
                if t.attachments:
                    for fname in t.attachments.split(','):
                        fpath = os.path.join(UPLOAD_FOLDER, fname)
                        if os.path.exists(fpath):
                            os.remove(fpath)
                db.session.delete(t)
                db.session.commit()
            # refresh in-memory cache
            load_tasks()
            return jsonify({'success': True})
        elif idx is not None:
            idx = int(idx)
            if idx < 0 or idx >= len(tasks):
                return jsonify({'success': False, 'error': 'Invalid task index'}), 400
            for fname in tasks[idx].get('attachments', []):
                fpath = os.path.join(UPLOAD_FOLDER, fname)
                if os.path.exists(fpath):
                    os.remove(fpath)
            tasks.pop(idx)
            save_tasks()
            return jsonify({'success': True, 'legacy': True})
        else:
            return jsonify({'success': False, 'error': 'Missing task identifier'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



# --- Persistent Storage Helpers ---
def load_tasks():
    global tasks, next_task_id
    try:
        with app.app_context():
            db_tasks = ItemDB.query.order_by(ItemDB.id.asc()).all()
            tasks.clear()
            max_id = 0
            for t in db_tasks:
                task_dict = {
                    'id': t.id,
                    'user_id': t.user_id,
                    'name': t.name,
                    'phase': t.phase,
                    'start': t.start or '',
                    'duration': t.duration or '',
                    'responsible': t.responsible or '',
                    'status': t.status or 'Not Started',
                    'percent_complete': t.percent_complete or '0',
                    'milestone': t.milestone or '',
                    'parent': t.parent,
                    'depends_on': t.depends_on or '',
                    'resources': t.resources or '',
                    'notes': t.notes or '',
                    'pdf_page': t.pdf_page or '',
                    'pdf_file': getattr(t, 'pdf_file', '') or '',
                    'external_item': getattr(t, 'external_item', False),
                    'external_task': getattr(t, 'external_item', False),  # legacy alias
                    'external_milestone': t.external_milestone,
                    'document_links': [d for d in (t.document_links.split(',') if t.document_links else []) if d],
                    'attachments': [a for a in (t.attachments.split(',') if t.attachments else []) if a],
                    'shared_with': [s for s in (t.shared_with.split(',') if t.shared_with else []) if s],
                }
                max_id = max(max_id, t.id)
                tasks.append(task_dict)
            next_task_id = max_id + 1
    except Exception as e:
        print('[ERROR] load_tasks DB:', e)

def save_tasks():
    try:
        with app.app_context():
            existing = {t.id: t for t in ItemDB.query.all()}
            for t in tasks:
                rec = existing.get(t['id'])
                doc_links = ','.join(t.get('document_links', []))
                attach = ','.join(t.get('attachments', []))
                shared = ','.join(t.get('shared_with', []))
                if rec:
                    rec.user_id = t.get('user_id')
                    rec.name = t.get('name')
                    rec.phase = t.get('phase')
                    rec.start = t.get('start')
                    rec.duration = t.get('duration')
                    rec.responsible = t.get('responsible')
                    rec.status = t.get('status')
                    rec.percent_complete = t.get('percent_complete')
                    rec.milestone = t.get('milestone')
                    rec.parent = t.get('parent')
                    rec.depends_on = t.get('depends_on')
                    rec.resources = t.get('resources')
                    rec.notes = t.get('notes')
                    rec.pdf_page = t.get('pdf_page')
                    if 'pdf_file' in t:
                        rec.pdf_file = t.get('pdf_file')
                    rec.external_item = t.get('external_item', t.get('external_task', False))
                    rec.external_milestone = t.get('external_milestone', False)
                    rec.document_links = doc_links
                    rec.attachments = attach
                    rec.shared_with = shared
                else:
                    db.session.add(ItemDB(
                        id=t['id'],
                        user_id=t.get('user_id'),
                        name=t.get('name'),
                        phase=t.get('phase'),
                        start=t.get('start'),
                        duration=t.get('duration'),
                        responsible=t.get('responsible'),
                        status=t.get('status'),
                        percent_complete=t.get('percent_complete'),
                        milestone=t.get('milestone'),
                        parent=t.get('parent'),
                        depends_on=t.get('depends_on'),
                        resources=t.get('resources'),
                        notes=t.get('notes'),
                        pdf_page=t.get('pdf_page'),
                        pdf_file=t.get('pdf_file'),
                        external_item=t.get('external_item', t.get('external_task', False)),
                        external_milestone=t.get('external_milestone', False),
                        document_links=doc_links,
                        attachments=attach,
                        shared_with=shared,
                    ))
            db.session.commit()
    except Exception as e:
        print('[ERROR] save_tasks DB:', e)

# --- Delete Attachment from Task ---
@app.route('/delete_attachment', methods=['POST'])
def delete_attachment():
    data = request.json
    task_idx = data.get('task_idx')
    filename = data.get('filename')
    if task_idx is None or filename is None:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    try:
        task_idx = int(task_idx)
        task = tasks[task_idx]
        if 'attachments' in task and filename in task['attachments']:
            task['attachments'].remove(filename)
            # Remove file from disk if it exists
            fpath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(fpath):
                os.remove(fpath)
            save_tasks()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Attachment not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Calendar export (iCalendar .ics) ---
@app.route('/calendar_export')
def calendar_export():
    def to_ics_datetime(dt):
        return dt.strftime('%Y%m%dT%H%M%S')
# --- Project Export as ZIP (JSON + Attachments) ---
import zipfile

@app.route('/download_project_zip')
def download_project_zip():
    # Prepare in-memory zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add project.json
        project_json = json.dumps(tasks, indent=2).encode('utf-8')
        zf.writestr('project.json', project_json)
        # Add all unique attachments referenced in tasks
        added = set()
        for t in tasks:
            for fname in t.get('attachments', []):
                if fname and fname not in added:
                    fpath = os.path.join(UPLOAD_FOLDER, fname)
                    if os.path.exists(fpath):
                        zf.write(fpath, arcname=os.path.join('attachments', fname))
                        added.add(fname)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='project_bundle.zip', mimetype='application/zip')
    ics_str = '\r\n'.join(ics)
    return Response(ics_str, mimetype='text/calendar', headers={
        'Content-Disposition': 'attachment; filename=project.ics'
    })

# --- Critical Path Calculation ---
def compute_critical_path(tasks):
    # Build task dict by name
    task_dict = {t['name']: t for t in tasks}
    # Build adjacency and reverse adjacency (for dependencies)
    adj = {t['name']: [] for t in tasks}
    rev_adj = {t['name']: [] for t in tasks}
    for t in tasks:
        @app.route('/migrate_legacy_json')
        @login_required
        def migrate_legacy_json():
            return jsonify({'success': False, 'error': 'Legacy JSON migration disabled; database is authoritative.'}), 410
        # Add phase as a top-level row (no date, no duration)
        all_tasks.append({
            'name': phase,
            'start': None,
            'duration': 0,
            'is_milestone': False,
            'is_phase': True,
            'external_task': False,
            'external_milestone': False
        })
        # Find top-level tasks (no parent)
        top_level = [t for t in phase_tasks if not t.get('parent') or t.get('parent') in ('', None, 'None')]
        for t in top_level:
            collect(t, all_tasks, 1)
    return all_tasks

@app.route('/gantt')
@login_required
def gantt_page():
    load_tasks()
    return render_template('gantt.html', tasks=tasks)

# --- Interactive Gantt (frontend JS-based) ---
@app.route('/gantt_interactive')
@login_required
def gantt_interactive_page():
    load_tasks()
    return render_template('gantt_interactive.html')

@app.route('/gantt_data')
@login_required
def gantt_data():
    """Return task data formatted for interactive Gantt usage.
    Each task includes computed finish date (start + duration days) and flags.
    Milestones represented with finish == start.
    """
    load_tasks()
    out = []
    for t in tasks:
        start = t.get('start')
        duration_raw = t.get('duration', 0)
        try:
            duration = int(duration_raw) if str(duration_raw).strip() != '' else 0
        except Exception:
            duration = 0
        finish = None
        if start:
            try:
                dt = datetime.strptime(start, '%Y-%m-%d')
                if t.get('milestone') or t.get('external_milestone'):
                    finish_dt = dt  # zero-length for milestone
                else:
                    finish_dt = dt + timedelta(days=duration if duration > 0 else 0)
                finish = finish_dt.strftime('%Y-%m-%d')
            except Exception:
                finish = start
        try:
            pc_val = float(t.get('percent_complete', 0))
        except Exception:
            pc_val = 0.0
        out.append({
            'id': t.get('id'),
            'name': t.get('name'),
            'phase': t.get('phase') or 'No Phase',
            'start': start,
            'finish': finish,
            'duration': duration,
            'percent_complete': pc_val,
            'status': t.get('status'),
            'milestone': bool(t.get('milestone')) or bool(t.get('external_milestone')),
            'external_task': bool(t.get('external_item') or t.get('external_task')),
            'external_milestone': bool(t.get('external_milestone')),
            'depends_on': t.get('depends_on'),
            'parent': t.get('parent'),
            'responsible': t.get('responsible'),
            'notes': t.get('notes'),
            'resources': t.get('resources'),
        })
    return jsonify(out)

@app.route('/gantt.png')
def gantt_chart():
    print("[DEBUG] Entered gantt_chart route")
    try:
        print("[DEBUG] Tasks before rendering Gantt chart:", json.dumps(tasks, indent=2, ensure_ascii=False))
        from flask import request as flask_request
        # Filtering: allow hiding external tasks/milestones
        hide_external = flask_request.args.get('hide_external', '0') in ('1', 'true', 'True')
        base_tasks = tasks
        if hide_external:
            base_tasks = [t for t in tasks if not (t.get('external_item') or t.get('external_task')) and not t.get('external_milestone')]
        parsed = parse_tasks_for_gantt(base_tasks)
        critical = compute_critical_path(tasks)
        fig, ax = plt.subplots(figsize=(24, 12))
        plt.rcParams.update({'font.size': 20})
        # Get color scheme from query params or use defaults
        primary_color = flask_request.args.get('primary', '#4287f5')
        secondary_color = flask_request.args.get('secondary', '#FF8200')
        if not parsed:
            ax.text(0.5, 0.5, 'No tasks to display', ha='center', va='center', fontsize=16, color='gray', transform=ax.transAxes)
            ax.set_xlabel('Date')
            fig.tight_layout()
        else:
            names = [t['name'] for t in parsed]
            # For phases, no start/duration; for tasks/sub-tasks, as before
            starts = [mdates.date2num(t['start']) if t.get('start') else None for t in parsed]
            durations = [int(t['duration']) if not isinstance(t['duration'], int) else t['duration'] for t in parsed]
            y_pos = list(range(len(parsed)))
            for i, t in enumerate(parsed):
                if t.get('is_phase'):
                    # Draw phase as a label only
                    ax.text(0, i, t['name'], va='center', ha='left', fontsize=18, fontweight='bold', color='black', bbox=dict(facecolor='#f0f0f0', edgecolor='gray', boxstyle='round,pad=0.2'))
                elif t.get('is_milestone'):
                    # External milestones forced red
                    milestone_color = 'red' if t.get('external_milestone') else secondary_color
                    ax.scatter(starts[i] + durations[i], i, marker='D', s=140, color=milestone_color, edgecolor='black', zorder=6,
                               label='Milestone' if i == 0 else "")
                else:
                    # Find the original task to get percent_complete
                    task_name = t['name'].lstrip()
                    orig_task = next((task for task in tasks if task['name'] == task_name), None)
                    try:
                        percent = float(orig_task.get('percent_complete', 0)) if orig_task else 0
                    except Exception:
                        percent = 0
                    percent = max(0, min(percent, 100))
                    dur = int(t['duration']) if not isinstance(t['duration'], int) else t['duration']
                    done_dur = dur * percent / 100.0
                    # External tasks always red full bar
                    if t.get('external_item') or t.get('external_task'):
                        ax.barh(i, dur, left=starts[i], height=0.45, align='center', color='red', edgecolor='black', hatch='///')
                    else:
                        # Draw completed (primary color) part
                        if done_dur > 0:
                            ax.barh(i, done_dur, left=starts[i], height=0.4, align='center', color=primary_color, edgecolor='black')
                        # Draw remaining (secondary color) part
                        if done_dur < dur:
                            ax.barh(i, dur - done_dur, left=starts[i] + done_dur, height=0.4, align='center', color=secondary_color, edgecolor='black')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names)
            ax.set_xlabel('Date')
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            fig.autofmt_xdate()
            ax.invert_yaxis()
            # Draw parent-child arrows
            name_to_info = {t['name'].lstrip(): (i, starts[i], durations[i]) for i, t in enumerate(parsed) if not t.get('is_phase')}
            for t in tasks:
                parent = t.get('parent')
                if parent and parent not in ('', None, 'None'):
                    child_name = t['name']
                    for i, pt in enumerate(parsed):
                        if pt['name'].lstrip() == child_name:
                            child_idx = i
                            break
                    else:
                        continue
                    for j, pt in enumerate(parsed):
                        if pt['name'].lstrip() == parent:
                            parent_idx = j
                            break
                    else:
                        continue
                    parent_y = parent_idx
                    child_y = child_idx
                    parent_end = starts[parent_idx] + durations[parent_idx]
                    child_start = starts[child_idx]
                    ax.annotate('', xy=(child_start, child_y), xytext=(parent_end, parent_y),
                                arrowprops=dict(arrowstyle='->', color='blue', lw=1.5, shrinkA=5, shrinkB=5))
            # Draw dependency arrows (depends_on)
            for t in tasks:
                dep = t.get('depends_on')
                if dep and dep not in ('', None, 'None'):
                    child_name = t['name']
                    dep_name = dep
                    for i, pt in enumerate(parsed):
                        if pt['name'].lstrip() == child_name:
                            child_idx = i
                            break
                    else:
                        continue
                    for j, pt in enumerate(parsed):
                        if pt['name'].lstrip() == dep_name:
                            dep_idx = j
                            break
                    else:
                        continue
                    dep_y = dep_idx
                    child_y = child_idx
                    dep_end = starts[dep_idx] + durations[dep_idx]
                    child_start = starts[child_idx]
                    ax.annotate('', xy=(child_start, child_y), xytext=(dep_end, dep_y),
                                arrowprops=dict(arrowstyle='->', color='red', lw=1.5, linestyle='dashed', shrinkA=5, shrinkB=5))
            fig.tight_layout()
            # Legend creation
            import matplotlib.patches as mpatches
            legend_items = []
            legend_items.append(mpatches.Patch(color=primary_color, label='Completed Portion'))
            legend_items.append(mpatches.Patch(color=secondary_color, label='Remaining Portion'))
            legend_items.append(mpatches.Patch(facecolor='red', edgecolor='black', hatch='///', label='External Task'))
            legend_items.append(plt.Line2D([0],[0], marker='D', color='w', markerfacecolor=secondary_color, markeredgecolor='black', markersize=12, label='Milestone'))
            legend_items.append(plt.Line2D([0],[0], marker='D', color='w', markerfacecolor='red', markeredgecolor='black', markersize=12, label='External Milestone'))
            legend_items.append(plt.Line2D([0],[0], color='blue', lw=2, label='Parent → Child'))
            legend_items.append(plt.Line2D([0],[0], color='red', lw=2, linestyle='dashed', label='Dependency'))
            ax.legend(handles=legend_items, loc='upper left', bbox_to_anchor=(1.01, 1), frameon=True, title='Legend')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return Response(buf.getvalue(), mimetype='image/png')
    except Exception as e:
        print("[ERROR] Exception in gantt_chart:", str(e))
        import traceback
        traceback.print_exc()
        return Response('Error rendering Gantt chart', mimetype='text/plain')

@app.route('/gantt_export/<fmt>')
def gantt_export(fmt):
    parsed = parse_tasks_for_gantt(tasks)
    fig, ax = plt.subplots(figsize=(8, 4))
    if not parsed:
        ax.text(0.5, 0.5, 'No tasks to display', ha='center', va='center', fontsize=16, color='gray', transform=ax.transAxes)
        ax.set_xlabel('Date')
        fig.tight_layout()
    else:
        names = [t['name'] for t in parsed]
        starts = [mdates.date2num(t['start']) for t in parsed]
        durations = [t['duration'] for t in parsed]
        y_pos = list(range(len(parsed)))
        for i, t in enumerate(parsed):
            ax.barh(i, t['duration'], left=starts[i], height=0.4, align='center', color='#FF8200', edgecolor='black')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel('Date')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        ax.invert_yaxis()
        # Draw parent-child arrows
        name_to_info = {t['name'].lstrip(): (i, starts[i], durations[i]) for i, t in enumerate(parsed)}
        for tsk in tasks:
            parent = tsk.get('parent')
            if parent:
                child_name = tsk['name']
                for i, pt in enumerate(parsed):
                    if pt['name'].lstrip() == child_name:
                        child_idx = i
                        break
                else:
                    continue
                for j, pt in enumerate(parsed):
                    if pt['name'].lstrip() == parent:
                        parent_idx = j
                        break
                else:
                    continue
                parent_y = parent_idx
                child_y = child_idx
                parent_end = starts[parent_idx] + durations[parent_idx]
                child_start = starts[child_idx]
                ax.annotate('', xy=(child_start, child_y), xytext=(parent_end, parent_y),
                            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5, shrinkA=5, shrinkB=5))
        fig.tight_layout()
    buf = io.BytesIO()
    if fmt == 'pdf':
        plt.savefig(buf, format='pdf')
        plt.close(fig)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name='project_timeline.pdf', mimetype='application/pdf')
    else:
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name='project_timeline.png', mimetype='image/png')

@app.route('/download_csv')
def download_csv():
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=['name', 'responsible', 'start', 'duration', 'depends_on', 'resources', 'notes', 'pdf_page', 'parent', 'external_task', 'external_milestone'])
    writer.writeheader()
    for t in tasks:
        row = {k: t.get(k, '') for k in ['name', 'responsible', 'start', 'duration', 'depends_on', 'resources', 'notes', 'pdf_page', 'parent', 'external_task', 'external_milestone']}
        writer.writerow(row)
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = 'attachment; filename=project.csv'
    output.headers['Content-type'] = 'text/csv'
    return output

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    global tasks
    load_tasks()
    load_phases()
    load_settings()
    # multi-PDF: list all uploaded pdfs
    try:
        pdf_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.pdf')]
    except Exception:
        pdf_files = []
    pdf_uploaded = len(pdf_files) > 0
    parent_options = [('', 'None')] + [(t['name'], t['name']) for t in tasks]
    if request.method == 'POST':
        print("[DEBUG] POST request received at index route.")
        print(f"[DEBUG] request.files: {request.files}")
        print(f"[DEBUG] request.form: {request.form}")
        if 'pdf' in request.files:
            print("[DEBUG] Entered PDF upload branch.")
            pdf = request.files['pdf']
            if pdf and pdf.filename.lower().endswith('.pdf'):
                safe_name = pdf.filename.replace('..', '').replace('/', '_').replace('\\', '_')
                pdf.save(os.path.join(UPLOAD_FOLDER, safe_name))
            return redirect(url_for('index'))
        if 'project_upload' in request.files:
            print("[DEBUG] Entered project_upload branch.")
            f = request.files['project_upload']
            if request.method == 'POST':
                if 'pdf' in request.files:
                    print("[DEBUG] Entered nested PDF upload branch.")
                    pdf = request.files['pdf']
                    if pdf and pdf.filename.lower().endswith('.pdf'):
                        pdf.save(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
                    return redirect(url_for('index'))
                if 'project_upload' in request.files:
                    print("[DEBUG] Entered nested project_upload branch.")
                    f = request.files['project_upload']
                    if f and f.filename.lower().endswith('.json'):
                        try:
                            data = json.load(f)
                            if isinstance(data, list):
                                tasks.clear()
                                for t in data:
                                    for k, default in [
                                        ('name', ''),
                                        ('responsible', ''),
                                        ('start', ''),
                                        ('duration', ''),
                                        ('depends_on', ''),
                                        ('resources', ''),
                                        ('notes', ''),
                                        ('pdf_page', ''),
                                        ('parent', ''),
                                        ('status', 'Not Started'),
                                        ('percent_complete', '0'),
                                        ('milestone', ''),
                                        ('attachments', []),
                                        ('document_links', []),
                                        ('external_task', False),
                                        ('external_milestone', False),
                                    ]:
                                        if k not in t:
                                            t[k] = default
                                    if not isinstance(t.get('attachments', []), list):
                                        if isinstance(t['attachments'], str) and t['attachments'].strip() == '':
                                            t['attachments'] = []
                                        elif isinstance(t['attachments'], str):
                                            t['attachments'] = [t['attachments']]
                                        else:
                                            t['attachments'] = list(t['attachments']) if t['attachments'] else []
                                    if not isinstance(t.get('document_links', []), list):
                                        if isinstance(t['document_links'], str) and t['document_links'].strip() == '':
                                            t['document_links'] = []
                                        elif isinstance(t['document_links'], str):
                                            t['document_links'] = [t['document_links']]
                                        else:
                                            t['document_links'] = list(t['document_links']) if t['document_links'] else []
                                tasks.extend(data)
                                save_tasks()
                                flash('Project loaded!')
                                load_tasks()
                        except Exception:
                            flash('Invalid project file.')
                    return redirect(url_for('index'))
                # Add new task from form
                print("[DEBUG] Entered new task creation branch.")
        # Unified task form (matching tasks tab)
                name = request.form.get('name', '').strip()
                phase = request.form.get('phase', '').strip()
                share_with = request.form.get('share_with', '').strip()
                responsible = request.form.get('responsible', '').strip()
                start = request.form.get('start', '').strip()
                duration = request.form.get('duration', '').strip()
                percent_complete = request.form.get('percent_complete', '0').strip()
                status = request.form.get('status', '').strip() or 'Not Started'
                depends_on = request.form.get('depends_on', '').strip()
                resources = request.form.get('resources', '').strip()
                notes = request.form.get('notes', '').strip()
                pdf_page = request.form.get('pdf_page', '').strip()
                pdf_file = request.form.get('pdf_file', '').strip()
                parent = request.form.get('parent', '').strip()
                milestone = request.form.get('milestone', '').strip()
        document_links_raw = request.form.get('document_links') or request.form.get('document_link', '')
        document_links = document_links_raw.strip()
        links_list = [l.strip() for l in document_links.split(',') if l.strip()]
        external_task = True if request.form.get('external_task') == 'on' else False
        external_milestone = True if request.form.get('external_milestone') == 'on' else False
        # Share_with usernames -> ids
        share_with_ids = []
        if share_with:
            load_users()
            for uname in [u.strip() for u in share_with.split(',') if u.strip()]:
                user = next((u for u in users if u['username'] == uname), None)
                if user:
                    share_with_ids.append(user['id'])
        # Attachments (use 'attachments' field name like tasks tab)
        attachment_filenames = []
        if 'attachments' in request.files:
            for attachment in request.files.getlist('attachments'):
                if attachment and attachment.filename:
                    safe_name = attachment.filename.replace('..', '').replace('/', '_').replace('\\', '_')
                    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
                    attachment.save(save_path)
                    attachment_filenames.append(safe_name)
        if attachment_filenames:
            print(f"[DEBUG] Saved attachments for task '{name}': {attachment_filenames}")
        # Automatically set status based on percent_complete
        try:
            percent_val = float(percent_complete)
        except Exception:
            percent_val = 0
        if percent_val >= 100:
            status = 'Completed'
        elif percent_val > 0:
            status = 'In Progress'
        else:
            status = 'Not Started'
        # If depends_on is set, automatically set start date to the day after the dependency ends
        auto_start = start
        if depends_on:
            dep_task = next((t for t in tasks if t['name'] == depends_on), None)
            if dep_task:
                try:
                    dep_start = datetime.strptime(dep_task['start'], '%Y-%m-%d')
                    dep_duration = int(dep_task['duration'])
                    dep_end = dep_start + timedelta(days=dep_duration)
                    auto_start = dep_end.strftime('%Y-%m-%d')
                except Exception:
                    pass
        edit_idx = request.form.get('edit_idx', '').strip()
        changed = False
        if name and duration and auto_start:
            global next_task_id
            # If editing, merge new attachments with existing ones
            if edit_idx.isdigit() and int(edit_idx) < len(tasks):
                if not can_edit():
                    flash('Editing is restricted to admins.')
                    return redirect(url_for('index'))
                old_task = tasks[int(edit_idx)]
                merged_attachments = list(old_task.get('attachments', []))
                for fname in attachment_filenames:
                    if fname not in merged_attachments:
                        merged_attachments.append(fname)
                # If the name changed, update all children to point to the new id as parent
                old_id = old_task.get('id')
                if old_id:
                    for t in tasks:
                        if t.get('parent') == old_id:
                            t['parent'] = old_id
                new_task = {
                    'id': old_task['id'],
                    'name': name,
                    'responsible': responsible,
                    'start': auto_start,
                    'duration': duration,
                    'depends_on': depends_on,
                    'resources': resources,
                    'notes': notes,
                    'pdf_page': pdf_page,
                    'pdf_file': pdf_file,
                    'status': status,
                    'percent_complete': percent_complete,
                    'parent': parent,
                    'milestone': milestone,
                    'attachments': merged_attachments,
                    'document_links': links_list,
                    'phase': phase,
                    'shared_with': share_with_ids,
                    'external_task': external_task,
                    'external_milestone': external_milestone,
                }
                tasks[int(edit_idx)] = new_task
                changed = True
            else:
                if not can_edit():
                    flash('Editing is restricted to admins.')
                    return redirect(url_for('index'))
                # New task: always set attachments field (even if empty)
                new_task = {
                    'id': next_task_id,
                    'user_id': current_user.get_id() if current_user.is_authenticated else None,
                    'name': name,
                    'responsible': responsible,
                    'start': auto_start,
                    'duration': duration,
                    'depends_on': depends_on,
                    'resources': resources,
                    'notes': notes,
                    'pdf_page': pdf_page,
                    'pdf_file': pdf_file,
                    'status': status,
                    'percent_complete': percent_complete,
                    'parent': parent,
                    'milestone': milestone,
                    'attachments': attachment_filenames,
                    'document_links': links_list,
                    'external_task': external_task,
                    'external_milestone': external_milestone,
                    'phase': phase,
                    'shared_with': share_with_ids,
                }
                tasks.append(new_task)
                next_task_id += 1
                changed = True
        print(f"[DEBUG] changed={changed}, name='{name}', duration='{duration}', auto_start='{auto_start}'")
        if changed:
            print("[DEBUG] New task form submitted.")
            print(f"[DEBUG] Form data: {request.form}")
            print(f"[DEBUG] New task: {new_task}")
            print(f"[DEBUG] Task list before save: {tasks}")
            save_tasks()
        return redirect(url_for('index'))
    # Global phases: show all phases (no longer filtered per-user)
    can_edit_flag = can_edit()
    return render_template('index.html', tasks=tasks, pdf_uploaded=pdf_uploaded, parent_options=parent_options, phases=phases, can_edit_flag=can_edit_flag, pdf_files=pdf_files)
    # ...existing code...
# --- Update Task Status (AJAX for Kanban drag-and-drop) ---
@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    data = request.get_json()
    print('[DEBUG] /update_task_status called with:', data)
    try:
        task_id = int(data.get('id', -1))
    except Exception as e:
        print('[DEBUG] Invalid task id:', data.get('id'))
        return jsonify({'success': False, 'error': 'Invalid task id'})
    new_status = data.get('status')
    with app.app_context():
        rec = ItemDB.query.get(task_id)
        if not rec:
            print(f"[DEBUG] Task id {task_id} not found in DB")
            return jsonify({'success': False, 'error': 'Task not found'})
        if not getattr(current_user, 'is_authenticated', False):
            return jsonify({'success': False, 'error': 'Auth required'}), 401
        if not getattr(current_user, 'is_admin', False):
            if rec.user_id != current_user.get_id() or not can_edit():
                return jsonify({'success': False, 'error': 'Not authorized'}), 403
        rec.status = new_status
        if new_status == 'Completed':
            rec.percent_complete = 100
        elif new_status == 'Not Started':
            rec.percent_complete = 0
        db.session.commit()
    load_tasks()
    return jsonify({'success': True})

# --- Update Task Fields (start, duration, percent_complete) for interactive Gantt ---
@app.route('/update_task_fields', methods=['POST'])
@login_required
def update_task_fields():
    data = request.get_json(force=True, silent=True) or {}
    task_id = data.get('id')
    if task_id is None:
        return jsonify({'success': False, 'error': 'Missing id'}), 400
    try:
        task_id = int(task_id)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid id'}), 400
    start = data.get('start')  # YYYY-MM-DD
    duration = data.get('duration')
    percent = data.get('percent_complete')
    with app.app_context():
        rec = ItemDB.query.get(task_id)
        if not rec:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        # Authorization: admin or owner + can_edit
        owner_id = rec.user_id or ''
        user_rec = next((u for u in users if str(u['id']) == str(current_user.get_id())), None)
        is_admin = user_rec.get('is_admin', False) if user_rec else False
        if not is_admin:
            if owner_id and owner_id != current_user.get_id():
                return jsonify({'success': False, 'error': 'Not authorized'}), 403
            if not can_edit():
                return jsonify({'success': False, 'error': 'Editing restricted'}), 403
        # Apply updates
        if start:
            try:
                datetime.strptime(start, '%Y-%m-%d')
                rec.start = start
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid start date'}), 400
        if duration is not None:
            try:
                d = int(duration)
                if d < 0:
                    return jsonify({'success': False, 'error': 'Duration cannot be negative'}), 400
                rec.duration = d
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid duration'}), 400
        if percent is not None:
            try:
                p = float(percent)
                p = max(0, min(100, p))
                rec.percent_complete = p
                if p >= 100:
                    rec.status = 'Completed'
                elif p > 0 and (rec.status == 'Not Started'):
                    rec.status = 'In Progress'
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid percent_complete'}), 400
        # Dependency constraint enforcement
        if rec.depends_on:
            dep = TaskDB.query.filter_by(name=rec.depends_on).first()
            if dep and dep.start:
                try:
                    dep_start_dt = datetime.strptime(dep.start, '%Y-%m-%d')
                    dep_dur = int(dep.duration or 0)
                    dep_end_dt = dep_start_dt + timedelta(days=dep_dur)
                    if rec.start:
                        this_start_dt = datetime.strptime(rec.start, '%Y-%m-%d')
                        if this_start_dt < dep_end_dt:
                            return jsonify({'success': False, 'error': 'Dependency violation', 'dependency_end': dep_end_dt.strftime('%Y-%m-%d')}), 409
                except Exception:
                    pass
        db.session.commit()
        # Refresh in-memory cache
        load_tasks()
        # Find updated task dict
        updated = next((t for t in tasks if t['id'] == rec.id), None)
        return jsonify({'success': True, 'start': updated.get('start'), 'duration': updated.get('duration'), 'percent_complete': updated.get('percent_complete')})

@app.route('/download_project')
def download_project():
    buf = io.BytesIO()
    buf.write(json.dumps(tasks, indent=2).encode('utf-8'))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='project.json', mimetype='application/json')

@app.route('/pdf')
def serve_pdf():
    return send_from_directory(UPLOAD_FOLDER, PDF_FILENAME)

# Serve arbitrary uploaded PDF (simple sanitization)
@app.route('/pdf/<path:filename>')
def serve_named_pdf(filename):
    safe = filename.replace('..','').replace('\\','_').replace('/', '_')
    return send_from_directory(UPLOAD_FOLDER, safe)

if __name__ == '__main__':
    load_tasks()
    app.run(debug=True)