"""initial schema: auth_users, refresh_tokens, login_attempts

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    auth_user_status = postgresql.ENUM(
        "active", "locked", "suspended", "deleted",
        name="auth_user_status",
    )
    auth_user_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_algo_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            postgresql.ENUM("active", "locked", "suspended", "deleted", name="auth_user_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("failed_login_attempts >= 0", name="ck_auth_users_failed_attempts_nonneg"),
        sa.UniqueConstraint("email", name="uq_auth_users_email"),
        sa.UniqueConstraint("phone_number", name="uq_auth_users_phone_number"),
    )
    op.create_index("ix_auth_users_status", "auth_users", ["status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "auth_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_token_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_refresh_tokens_expiry_after_issue"),
    )
    op.create_index("ix_refresh_tokens_auth_user_id", "refresh_tokens", ["auth_user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "auth_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email_attempted", postgresql.CITEXT(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_attempts_auth_user_id", "login_attempts", ["auth_user_id"])
    op.create_index(
        "ix_login_attempts_ip_attempted_at", "login_attempts", ["ip_address", "attempted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_ip_attempted_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_auth_user_id", table_name="login_attempts")
    op.drop_table("login_attempts")

    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_auth_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_auth_users_status", table_name="auth_users")
    op.drop_table("auth_users")

    postgresql.ENUM(name="auth_user_status").drop(op.get_bind(), checkfirst=True)
