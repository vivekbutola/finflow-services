"""initial schema: users, addresses, kyc_profiles, user_preferences, notification_preferences

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

    user_status = postgresql.ENUM(
        "active", "inactive", "suspended", "deleted", name="user_status"
    )
    user_status.create(op.get_bind(), checkfirst=True)

    address_type = postgresql.ENUM(
        "residential", "billing", "business", "shipping", name="address_type"
    )
    address_type.create(op.get_bind(), checkfirst=True)

    kyc_status = postgresql.ENUM(
        "pending", "in_review", "verified", "rejected", name="kyc_status"
    )
    kyc_status.create(op.get_bind(), checkfirst=True)

    theme_preference = postgresql.ENUM(
        "light", "dark", "system", name="theme_preference"
    )
    theme_preference.create(op.get_bind(), checkfirst=True)

    # --- users ---------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("profile_photo_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "inactive", "suspended", "deleted",
                name="user_status", create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ux_users_auth_user_id", "users", ["auth_user_id"], unique=True)
    op.create_index("ix_users_status", "users", ["status"])

    # --- addresses -------------------------------------------------------
    op.create_table(
        "addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "address_type",
            postgresql.ENUM(
                "residential", "billing", "business", "shipping",
                name="address_type", create_type=False,
            ),
            nullable=False,
            server_default="residential",
        ),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("char_length(country) = 2", name="ck_addresses_country_iso2"),
    )
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])

    # --- kyc_profiles ------------------------------------------------------
    op.create_table(
        "kyc_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kyc_status",
            postgresql.ENUM(
                "pending", "in_review", "verified", "rejected",
                name="kyc_status", create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("pan_number", sa.String(length=10), nullable=True),
        sa.Column("aadhaar_last4", sa.String(length=4), nullable=True),
        sa.Column("verification_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "aadhaar_last4 IS NULL OR aadhaar_last4 ~ '^[0-9]{4}$'",
            name="ck_kyc_profiles_aadhaar_last4_format",
        ),
    )
    op.create_index("ux_kyc_profiles_user_id", "kyc_profiles", ["user_id"], unique=True)
    op.create_index("ix_kyc_profiles_kyc_status", "kyc_profiles", ["kyc_status"])

    # --- user_preferences ------------------------------------------------
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column(
            "theme",
            postgresql.ENUM("light", "dark", "system", name="theme_preference", create_type=False),
            nullable=False,
            server_default="system",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ux_user_preferences_user_id", "user_preferences", ["user_id"], unique=True)

    # --- notification_preferences -----------------------------------------
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ux_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ux_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("ux_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_index("ix_kyc_profiles_kyc_status", table_name="kyc_profiles")
    op.drop_index("ux_kyc_profiles_user_id", table_name="kyc_profiles")
    op.drop_table("kyc_profiles")

    op.drop_index("ix_addresses_user_id", table_name="addresses")
    op.drop_table("addresses")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ux_users_auth_user_id", table_name="users")
    op.drop_table("users")

    postgresql.ENUM(name="theme_preference").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="kyc_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="address_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="user_status").drop(op.get_bind(), checkfirst=True)
