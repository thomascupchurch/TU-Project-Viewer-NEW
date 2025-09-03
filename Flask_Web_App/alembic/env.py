from __future__ import annotations
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# This Alembic Config object, which provides access to the values within the .ini file.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def get_url():
    # Allow DATABASE_URL env var to override sqlite path
    return os.getenv('DATABASE_URL') or config.get_main_option('sqlalchemy.url')

# Import metadata from app models
# We try main app first, then MVP fallback.
try:
    from db import db as main_db  # existing main application db object
    target_metadata = main_db.Model.metadata
except Exception:
    try:
        from mvp_app import db as mvp_db
        target_metadata = mvp_db.Model.metadata
    except Exception:
        target_metadata = None

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
