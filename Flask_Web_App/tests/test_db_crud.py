import os, sys, importlib.util, pathlib, pytest

# Attempt normal simple import
app = db = UserDB = PhaseDB = ItemDB = SettingDB = None  # placeholders
try:
    from app import app, db, UserDB, PhaseDB, ItemDB, SettingDB  # type: ignore
except ModuleNotFoundError:
    project_root = pathlib.Path(__file__).parent.parent
    app_path = project_root / 'app.py'
    if app_path.exists():
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        spec = importlib.util.spec_from_file_location('app', str(app_path))
        module = importlib.util.module_from_spec(spec)  # type: ignore
        assert spec and spec.loader
        spec.loader.exec_module(module)  # type: ignore
        app = module.app
        db = module.db
        UserDB = module.UserDB
        PhaseDB = module.PhaseDB
        ItemDB = module.ItemDB
        SettingDB = module.SettingDB
    else:
        raise
from werkzeug.security import generate_password_hash

@pytest.fixture()
def client():
    app.config['TESTING'] = True
    # Use in-memory sqlite for tests
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app.test_client()

def test_user_crud(client):
    with app.app_context():
        u = UserDB(id='u1', username='tester', password_hash=generate_password_hash('Passw0rd!'), is_admin=False)
        db.session.add(u)
        db.session.commit()
    # Verify user exists via ORM
    assert UserDB.query.filter_by(username='tester').first() is not None
    # Update password
    u.password_hash = generate_password_hash('NewPassw0rd!')
    db.session.commit()
    updated = db.session.get(UserDB, 'u1')
    assert updated and updated.password_hash != ''
    # Delete user
    db.session.delete(updated)
    db.session.commit()
    assert db.session.get(UserDB, 'u1') is None

def test_phase_and_setting_crud(client):
    with app.app_context():
        db.session.add(PhaseDB(name='Initiation'))
        db.session.add(SettingDB(key='open_editing', value='1'))
        db.session.commit()
    # Validate creation
    assert PhaseDB.query.filter_by(name='Initiation').first() is not None
    setting = db.session.get(SettingDB, 'open_editing')
    assert setting and setting.value == '1'
    # Update setting
    s = db.session.get(SettingDB, 'open_editing')
    s.value = '0'
    db.session.commit()
    changed_setting = db.session.get(SettingDB, 'open_editing')
    assert changed_setting and changed_setting.value == '0'
    # Delete phase
    p = PhaseDB.query.filter_by(name='Initiation').first()
    db.session.delete(p)
    db.session.commit()
    assert PhaseDB.query.filter_by(name='Initiation').first() is None

def test_item_crud_and_dependencies(client):
    with app.app_context():
        # Seed user
        db.session.add(UserDB(id='u2', username='owner', password_hash=generate_password_hash('OwnerPass1!'), is_admin=True))
        db.session.commit()
    # Create items
    t1 = ItemDB(user_id='u2', name='Item A', start='2025-01-01', duration='5', status='Not Started', percent_complete='0')
    t2 = ItemDB(user_id='u2', name='Item B', start='2025-01-10', duration='3', status='Not Started', percent_complete='0', depends_on='Item A')
    db.session.add_all([t1, t2])
    db.session.commit()
    # Verify items loaded
    assert ItemDB.query.filter_by(name='Item A').first() is not None
    assert ItemDB.query.filter_by(name='Item B', depends_on='Item A').first() is not None
    # Update
    t1.status = 'Completed'
    t1.percent_complete = '100'
    db.session.commit()
    ta = ItemDB.query.filter_by(name='Item A').first()
    assert ta and ta.status == 'Completed'
    # Delete
    db.session.delete(t2)
    db.session.commit()
    assert ItemDB.query.filter_by(name='Item B').first() is None

def test_item_pdf_file_persistence(client):
    with app.app_context():
        # Seed user
        db.session.add(UserDB(id='u3', username='pdfuser', password_hash=generate_password_hash('PdfPass1!'), is_admin=False))
        db.session.commit()
        item = ItemDB(user_id='u3', name='Item PDF', start='2025-02-01', duration='2', status='Not Started', percent_complete='0', pdf_page='5', pdf_file='first.pdf')
        db.session.add(item)
        db.session.commit()
        fetched = ItemDB.query.filter_by(name='Item PDF').first()
        assert fetched is not None
        assert getattr(fetched, 'pdf_file', None) == 'first.pdf'
        # Update pdf_file
        fetched.pdf_file = 'second.pdf'
        db.session.commit()
    refetched = ItemDB.query.filter_by(name='Item PDF').first()
    assert refetched and refetched.pdf_file == 'second.pdf'
