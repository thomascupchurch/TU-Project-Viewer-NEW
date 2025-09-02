from datetime import datetime, UTC
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect

# SQLAlchemy instance
db = SQLAlchemy()

class UserDB(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(64), primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    reset_token = db.Column(db.String(128), nullable=True, index=True)
    reset_expires = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    # Primary relationship to items
    items = db.relationship('ItemDB', backref='owner', lazy=True)

    # Backward compatibility alias (read-only) for legacy code expecting user.tasks
    @property
    def tasks(self):
        return self.items

class PhaseDB(db.Model):
    __tablename__ = 'phases'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

# Primary Item model (renamed from legacy TaskDB)
class ItemDB(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    name = db.Column(db.String(300), nullable=False)
    phase = db.Column(db.String(200))
    start = db.Column(db.String(20))
    duration = db.Column(db.String(10))
    responsible = db.Column(db.String(120))
    status = db.Column(db.String(50))
    percent_complete = db.Column(db.String(10))
    milestone = db.Column(db.String(200))
    parent = db.Column(db.String(300))
    depends_on = db.Column(db.String(300))
    resources = db.Column(db.String(500))
    notes = db.Column(db.Text)
    pdf_page = db.Column(db.String(20))
    # New: reference to which PDF file the pdf_page refers to
    pdf_file = db.Column(db.String(400))  # filename stored in static/uploads
    external_item = db.Column(db.Boolean, default=False)
    external_milestone = db.Column(db.Boolean, default=False)
    document_links = db.Column(db.Text)
    attachments = db.Column(db.Text)
    shared_with = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

# Legacy model for migration reading only (do not use after migration)
class TaskDB(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64))
    name = db.Column(db.String(300), nullable=False)
    phase = db.Column(db.String(200))
    start = db.Column(db.String(20))
    duration = db.Column(db.String(10))
    responsible = db.Column(db.String(120))
    status = db.Column(db.String(50))
    percent_complete = db.Column(db.String(10))
    milestone = db.Column(db.String(200))
    parent = db.Column(db.String(300))
    depends_on = db.Column(db.String(300))
    resources = db.Column(db.String(500))
    notes = db.Column(db.Text)
    pdf_page = db.Column(db.String(20))
    external_task = db.Column(db.Boolean, default=False)
    external_milestone = db.Column(db.Boolean, default=False)
    document_links = db.Column(db.Text)
    attachments = db.Column(db.Text)
    shared_with = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class SettingDB(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500))

class AttachmentDB(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    filename = db.Column(db.String(400), nullable=False)
    original_name = db.Column(db.String(400))
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

# New: Contacts (project resource people)
class ContactDB(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200))
    company = db.Column(db.String(200))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(100))
    address = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

# New: Assets (uploaded generic resource files)
class AssetDB(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    filename = db.Column(db.String(400), nullable=False)
    original_name = db.Column(db.String(400))
    description = db.Column(db.String(400))
    size_bytes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

# Utility seed for first admin user if none exists

def ensure_admin_user(db_session):
    if not UserDB.query.filter_by(is_admin=True).first():
        u = UserDB(id='admin-seed', username='admin', password_hash=generate_password_hash('ChangeMe123!'), is_admin=True)
        db_session.add(u)
        db_session.commit()

def migrate_tasks_to_items(db_session):
    insp = inspect(db.engine)
    tables = insp.get_table_names()
    if 'tasks' in tables and 'items' not in tables:
        # create items table
        ItemDB.__table__.create(db.engine)
    # Ensure pdf_file column exists (schema evolution) for existing deployments
    if 'items' in tables:
        cols = [c['name'] for c in insp.get_columns('items')]
        if 'pdf_file' not in cols:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE items ADD COLUMN pdf_file VARCHAR(400)'))
            except Exception as e:
                print('[WARN] Unable to add pdf_file column (may already exist):', e)
    if 'tasks' in tables and 'items' in tables:
        # copy rows if items empty
        if db_session.query(ItemDB).count() == 0:
            for t in db_session.query(TaskDB).all():
                db_session.add(ItemDB(
                    id=t.id,
                    user_id=t.user_id,
                    name=t.name,
                    phase=t.phase,
                    start=t.start,
                    duration=t.duration,
                    responsible=t.responsible,
                    status=t.status,
                    percent_complete=t.percent_complete,
                    milestone=t.milestone,
                    parent=t.parent,
                    depends_on=t.depends_on,
                    resources=t.resources,
                    notes=t.notes,
                    pdf_page=t.pdf_page,
                    external_item=t.external_task,
                    external_milestone=t.external_milestone,
                    document_links=t.document_links,
                    attachments=t.attachments,
                    shared_with=t.shared_with,
                    created_at=t.created_at,
                ))
            db_session.commit()
