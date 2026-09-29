"""initial schema: wallets, wallet_ledger

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
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    wallet_status = postgresql.ENUM(
        "ACTIVE", "FROZEN", "CLOSED", name="wallet_status"
    )
    wallet_status.create(op.get_bind(), checkfirst=True)

    ledger_entry_type = postgresql.ENUM(
        "CREDIT", "DEBIT", name="ledger_entry_type"
    )
    ledger_entry_type.create(op.get_bind(), checkfirst=True)

    # --- wallets -----------------------------------------------------------
    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Numeric(precision=19, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            postgresql.ENUM("ACTIVE", "FROZEN", "CLOSED", name="wallet_status", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_wallets_balance_nonnegative"),
        sa.CheckConstraint("currency = 'INR'", name="ck_wallets_currency_inr_only"),
    )
    op.create_index("ux_wallets_user_id", "wallets", ["user_id"], unique=True)
    op.create_index("ux_wallets_wallet_id", "wallets", ["wallet_id"], unique=True)
    op.create_index("ix_wallets_status", "wallets", ["status"])

    # --- wallet_ledger -------------------------------------------------------
    op.create_table(
        "wallet_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_type",
            postgresql.ENUM("CREDIT", "DEBIT", name="ledger_entry_type", create_type=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("balance_before", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_wallet_ledger_amount_positive"),
        sa.CheckConstraint("balance_before >= 0", name="ck_wallet_ledger_balance_before_nonneg"),
        sa.CheckConstraint("balance_after >= 0", name="ck_wallet_ledger_balance_after_nonneg"),
    )
    op.create_index(
        "ix_wallet_ledger_wallet_id_created_at", "wallet_ledger", ["wallet_id", "created_at"]
    )
    op.create_index(
        "ux_wallet_ledger_wallet_reference",
        "wallet_ledger",
        ["wallet_id", "reference_id"],
        unique=True,
        postgresql_where=sa.text("reference_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_wallet_ledger_wallet_reference", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_wallet_id_created_at", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")

    op.drop_index("ix_wallets_status", table_name="wallets")
    op.drop_index("ux_wallets_wallet_id", table_name="wallets")
    op.drop_index("ux_wallets_user_id", table_name="wallets")
    op.drop_table("wallets")

    postgresql.ENUM(name="ledger_entry_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="wallet_status").drop(op.get_bind(), checkfirst=True)
