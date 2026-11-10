"""initial schema: transactions, transaction_audit

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

    transaction_status = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILED", "REVERSED", name="transaction_status"
    )
    transaction_status.create(op.get_bind(), checkfirst=True)

    # --- transactions -------------------------------------------------------
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("from_wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "SUCCESS", "FAILED", "REVERSED",
                name="transaction_status", create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("from_wallet_id != to_wallet_id", name="ck_transactions_distinct_wallets"),
    )
    op.create_index("ux_transactions_reference_id", "transactions", ["reference_id"], unique=True)
    op.create_index(
        "ix_transactions_from_wallet_id_created_at", "transactions", ["from_wallet_id", "created_at"]
    )
    op.create_index(
        "ix_transactions_to_wallet_id_created_at", "transactions", ["to_wallet_id", "created_at"]
    )
    op.create_index("ix_transactions_status", "transactions", ["status"])
    op.create_index(
        "ix_transactions_initiated_by_user_id", "transactions", ["initiated_by_user_id"]
    )

    # --- transaction_audit -----------------------------------------------
    op.create_table(
        "transaction_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_transaction_audit_transaction_id_timestamp",
        "transaction_audit",
        ["transaction_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_transaction_audit_transaction_id_timestamp", table_name="transaction_audit")
    op.drop_table("transaction_audit")

    op.drop_index("ix_transactions_initiated_by_user_id", table_name="transactions")
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_to_wallet_id_created_at", table_name="transactions")
    op.drop_index("ix_transactions_from_wallet_id_created_at", table_name="transactions")
    op.drop_index("ux_transactions_reference_id", table_name="transactions")
    op.drop_table("transactions")

    postgresql.ENUM(name="transaction_status").drop(op.get_bind(), checkfirst=True)
