import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction import Transaction, TransactionStatus


class TransactionRepository:
    """Persistence layer for `transactions`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, transaction_id: uuid.UUID) -> Transaction | None:
        result = await self._session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update_by_id(self, transaction_id: uuid.UUID) -> Transaction | None:
        """Pessimistic row lock, taken before mutating a transaction's
        status (e.g. during reversal) so two concurrent requests against the
        same transaction serialize at the database level."""
        result = await self._session.execute(
            select(Transaction).where(Transaction.id == transaction_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_reference_id(self, reference_id: str) -> Transaction | None:
        result = await self._session.execute(
            select(Transaction).where(Transaction.reference_id == reference_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        reference_id: str,
        from_wallet_id: uuid.UUID,
        to_wallet_id: uuid.UUID,
        amount,
        currency: str,
        initiated_by_user_id: uuid.UUID,
        status: TransactionStatus = TransactionStatus.PENDING,
    ) -> Transaction:
        transaction = Transaction(
            reference_id=reference_id,
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            amount=amount,
            currency=currency,
            initiated_by_user_id=initiated_by_user_id,
            status=status,
        )
        self._session.add(transaction)
        await self._session.flush()
        return transaction

    async def update_status(
        self,
        transaction: Transaction,
        *,
        status: TransactionStatus,
        failure_reason: str | None = None,
    ) -> Transaction:
        # `updated_at` is set explicitly here rather than relying solely on
        # the column's server-side `onupdate=func.now()`. Under AsyncSession,
        # a column whose new value is only known to the server (not set on
        # the Python side) is marked expired after flush; a later synchronous
        # attribute access -- e.g. Pydantic's `model_validate` serializing
        # the response -- then triggers an implicit lazy-load refresh, which
        # raises `MissingGreenlet` outside of a greenlet-spawned context.
        # Setting it here gives the ORM a known value so no refresh is ever
        # needed.
        transaction.status = status
        transaction.updated_at = datetime.now(timezone.utc)
        if failure_reason is not None:
            transaction.failure_reason = failure_reason
        await self._session.flush()
        return transaction

    async def list_paginated(
        self,
        *,
        status: TransactionStatus | None = None,
        wallet_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Transaction], int]:
        filters = []
        if status is not None:
            filters.append(Transaction.status == status)
        if wallet_id is not None:
            filters.append(
                (Transaction.from_wallet_id == wallet_id) | (Transaction.to_wallet_id == wallet_id)
            )

        count_stmt = select(func.count()).select_from(Transaction)
        for f in filters:
            count_stmt = count_stmt.where(f)
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = select(Transaction)
        for f in filters:
            list_stmt = list_stmt.where(f)
        list_stmt = (
            list_stmt.order_by(Transaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._session.execute(list_stmt)
        return list(result.scalars().all()), total
