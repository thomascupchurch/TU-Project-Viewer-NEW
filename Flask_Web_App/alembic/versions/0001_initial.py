"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-09-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('reset_token', sa.String(length=128)),
        sa.Column('reset_expires', sa.Float()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    op.create_table('phases',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=200), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table('tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=64)),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('phase', sa.String(length=200)),
        sa.Column('start', sa.String(length=20)),
        sa.Column('duration', sa.String(length=10)),
        sa.Column('responsible', sa.String(length=120)),
        sa.Column('status', sa.String(length=50)),
        sa.Column('percent_complete', sa.String(length=10)),
        sa.Column('milestone', sa.String(length=200)),
        sa.Column('parent', sa.String(length=300)),
        sa.Column('depends_on', sa.String(length=300)),
        sa.Column('resources', sa.String(length=500)),
        sa.Column('notes', sa.Text()),
        sa.Column('pdf_page', sa.String(length=20)),
        sa.Column('external_task', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('external_milestone', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('document_links', sa.Text()),
        sa.Column('attachments', sa.Text()),
        sa.Column('shared_with', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table('items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id')),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('phase', sa.String(length=200)),
        sa.Column('start', sa.String(length=20)),
        sa.Column('duration', sa.String(length=10)),
        sa.Column('responsible', sa.String(length=120)),
        sa.Column('status', sa.String(length=50)),
        sa.Column('percent_complete', sa.String(length=10)),
        sa.Column('milestone', sa.String(length=200)),
        sa.Column('parent', sa.String(length=300)),
        sa.Column('depends_on', sa.String(length=300)),
        sa.Column('resources', sa.String(length=500)),
        sa.Column('notes', sa.Text()),
        sa.Column('pdf_page', sa.String(length=20)),
        sa.Column('pdf_file', sa.String(length=400)),
        sa.Column('external_item', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('external_milestone', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('document_links', sa.Text()),
        sa.Column('attachments', sa.Text()),
        sa.Column('shared_with', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table('settings',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', sa.String(length=500)),
    )

    op.create_table('attachments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('filename', sa.String(length=400), nullable=False),
        sa.Column('original_name', sa.String(length=400)),
        sa.Column('uploaded_at', sa.DateTime()),
    )

    op.create_table('contacts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id')),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=200)),
        sa.Column('company', sa.String(length=200)),
        sa.Column('email', sa.String(length=200)),
        sa.Column('phone', sa.String(length=100)),
        sa.Column('address', sa.String(length=300)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table('assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id')),
        sa.Column('filename', sa.String(length=400), nullable=False),
        sa.Column('original_name', sa.String(length=400)),
        sa.Column('description', sa.String(length=400)),
        sa.Column('size_bytes', sa.Integer()),
        sa.Column('created_at', sa.DateTime()),
    )

def downgrade() -> None:
    for table in ['assets','contacts','attachments','settings','items','tasks','phases','users']:
        op.drop_table(table)
