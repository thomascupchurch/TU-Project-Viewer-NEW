import os, io, sys, importlib.util, pathlib, pytest

app = db = UserDB = ContactDB = AssetDB = None  # placeholders
try:
    from app import app, db, UserDB, ContactDB, AssetDB  # type: ignore
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
        ContactDB = module.ContactDB
        AssetDB = module.AssetDB
    else:
        raise
from werkzeug.security import generate_password_hash

def _seed_user(uid='uR', name='resuser'):
    db.session.add(UserDB(id=uid, username=name, password_hash=generate_password_hash('ResUser1!'), is_admin=True))
    db.session.commit()
    return uid

@pytest.fixture()
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.drop_all(); db.create_all()
        yield app.test_client()

def test_contact_crud(client):
    with app.app_context():
        _seed_user()
        c = ContactDB(user_id='uR', name='Alice', title='Mgr', company='Acme', email='a@x.com')
        db.session.add(c); db.session.commit()
        assert ContactDB.query.filter_by(name='Alice').first() is not None
        c.email = 'alice@acme.com'; db.session.commit()
        updated = ContactDB.query.filter_by(name='Alice').first()
        assert updated.email == 'alice@acme.com'
        db.session.delete(updated); db.session.commit()
        assert ContactDB.query.filter_by(name='Alice').first() is None

def test_asset_crud(client, tmp_path):
    with app.app_context():
        _seed_user('uA','assetuser')
        # Simulate upload: directly create record (bypassing file write for speed)
        a = AssetDB(user_id='uA', filename='doc.txt', original_name='doc.txt', description='test file', size_bytes=12)
        db.session.add(a); db.session.commit()
        assert AssetDB.query.filter_by(filename='doc.txt').first() is not None
        a.description = 'updated'; db.session.commit()
        again = AssetDB.query.filter_by(filename='doc.txt').first()
        assert again.description == 'updated'
        db.session.delete(again); db.session.commit()
        assert AssetDB.query.filter_by(filename='doc.txt').first() is None
