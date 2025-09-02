"""Shim so tests can import app when expecting a top-level module name.
Usage: from app_shim import app, db, UserDB, PhaseDB, ItemDB, SettingDB
Pytest can be adjusted to use this or we can rename file, but this keeps backward compat.
"""
from .app import app, db, UserDB, PhaseDB, ItemDB, SettingDB  # type: ignore
__all__ = ['app','db','UserDB','PhaseDB','ItemDB','SettingDB']
