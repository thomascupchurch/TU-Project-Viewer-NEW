# MVP Sub-Application

Minimal Flask app for rapid deployment while core app continues development.

## Features
- User registration & login (username + password)
- Simple per-user items list (CRUD: create, update title, delete)
- Bootstrap-based minimal UI
- Single SQLite database (default `mvp.db`)

## Run Locally
```bash
set FLASK_APP=wsgi:app
flask run --reload
```
(Windows PowerShell) `($env:FLASK_APP='wsgi:app'; flask run)`

## Pointing To Main App Database
If you want the MVP to share the main database so future expansion keeps data:
```
$env:MVP_DATABASE_URL = 'sqlite:///../app.db'
```
Make sure the path resolves from the `MVP` directory. Then start the app; `db.create_all()` will add only missing minimal tables if they do not exist.

## Deployment (PythonAnywhere)
1. Upload `MVP` folder.
2. Create a virtualenv & install deps: `pip install -r MVP/requirements.txt`.
3. Set WSGI configuration to point to `.../MVP/wsgi.py` with `app` callable.
4. (Optional) Set env var `MVP_DATABASE_URL` to production DB location.

## Next Steps / Extensibility
- Add Alembic migrations for versioned schema changes.
- Reuse full app's richer Item fields by expanding `Item` model (add columns; migrations required).
- Introduce API blueprint for SPA/JS clients.
- Add password reset + rate limiting (reuse logic from main app's auth blueprint).

## Testing Stub
You can create a `tests_mvp/` folder and spin up the factory with `create_app(testing=True)` for isolated unit tests.
