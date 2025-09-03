from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
import os

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
class User(db.Model, UserMixin):
    id = db.Column(db.String(64), primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('user.id'))
    name = db.Column(db.String(200), nullable=False)
    start = db.Column(db.String(20))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def create_app(testing=False):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','mvp-secret')
    db_url = os.environ.get('MVP_DATABASE_URL') or 'sqlite:///mvp.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if testing:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    db.init_app(app)
    login_manager.init_app(app)

    from .auth import auth_bp
    from .items import items_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)

    with app.app_context():
        db.create_all()

    @app.get('/')
    def index():
        return "MVP OK"  # simple health indicator

    return app
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
import os

# Single DB instance (shared for future expansion)
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

class User(db.Model, UserMixin):
    id = db.Column(db.String(64), primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('user.id'))
    name = db.Column(db.String(200), nullable=False)
    start = db.Column(db.String(20))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def create_app(testing=False):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','mvp-secret')
    db_url = os.environ.get('MVP_DATABASE_URL') or 'sqlite:///mvp.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if testing:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    db.init_app(app)
    login_manager.init_app(app)

    from .auth import auth_bp
    from .items import items_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)

    with app.app_context():
        db.create_all()

    @app.get('/')
    def index():
        return "MVP OK"  # simple health indicator

    return app
