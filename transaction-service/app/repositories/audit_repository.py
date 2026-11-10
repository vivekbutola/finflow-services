import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction_audit import TransactionAudit


class TransactionAuditRepository:
    """Append-only persistence layer for `transaction_audit`. No update or
    delete methods are exposed — matching the immutable-audit-trail
    requirement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        *,
        transaction_id: uuid.UUID,
        action: str,
        metadata: dict | None = None,
    ) -> TransactionAudit:
        entry = TransactionAudit(
            transaction_id=transaction_id,
            action=action,
            audit_metadata=metadata,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_transaction(self, transaction_id: uuid.UUID) -> list[TransactionAudit]:
        result = await self._session.execute(
            select(TransactionAudit)
            .where(TransactionAudit.transaction_id == transaction_id)
            .order_by(TransactionAudit.timestamp.asc())
        )
        return list(result.scalars().all())
