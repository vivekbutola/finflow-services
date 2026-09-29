import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.wallet_ledger import LedgerEntryType, WalletLedger


class WalletLedgerRepository:
    """Persistence layer for `wallet_ledger`. Append-only — no update/delete
    methods are exposed, matching the immutable-audit-trail requirement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_wallet_and_reference(
        self, wallet_id: uuid.UUID, reference_id: str
    ) -> WalletLedger | None:
        result = await self._session.execute(
            select(WalletLedger).where(
                WalletLedger.wallet_id == wallet_id,
                WalletLedger.reference_id == reference_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        wallet_id: uuid.UUID,
        entry_type: LedgerEntryType,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        reference_id: str | None,
    ) -> WalletLedger:
        entry = WalletLedger(
            wallet_id=wallet_id,
            entry_type=entry_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=reference_id,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
