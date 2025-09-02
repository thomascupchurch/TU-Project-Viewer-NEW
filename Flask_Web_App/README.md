# TU Project Viewer

Flask-based project/task viewer supporting:
- User authentication & admin management
- Phases and tasks (items) with dependencies and multi-PDF association
- Attachments & document links
- Resources page (Contacts & Assets upload/download/delete)

## Quick Start

```powershell
# Create & activate venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run (development)
python app.py  # or: $env:FLASK_APP="app"; flask run --reload
```

App will create `app.db` (SQLite) on first run. Default admin is auto-created if not present.

## Tests

```powershell
pytest -q
```

## Key Routes
- `/login`, `/register`, `/logout`
- `/items` (task CRUD)
- `/phases`
- `/resources` (contacts & assets)
- `/admin` (admin dashboard)

## Models (excerpt)
Located in `db.py`: `UserDB`, `PhaseDB`, `ItemDB`, `SettingDB`, `ContactDB`, `AssetDB`.

## Notes
- Legacy JSON migration code retained for reference.
- Tests use dynamic import fallback of `app.py` for resilience.

## Next Improvements
- Convert monolithic `app.py` into package modules (auth, items, resources).
- Replace in-memory caches with direct DB queries or a caching layer.
- Add integration tests for routes (Flask test client) beyond pure ORM CRUD.
