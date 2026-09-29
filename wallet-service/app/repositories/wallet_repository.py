import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.wallet import Wallet, WalletStatus


class WalletRepository:
    """Persistence layer for `wallets`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> Wallet | None:
        result = await self._session.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update_by_user_id(self, user_id: uuid.UUID) -> Wallet | None:
        """Takes a pessimistic row lock (SELECT ... FOR UPDATE) so concurrent
        credit/debit requests for the same wallet serialize at the database
        level. Combined with the ORM's optimistic `version` column as a
        defense-in-depth safety net."""
        result = await self._session.execute(
            select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: uuid.UUID) -> Wallet:
        wallet = Wallet(
            user_id=user_id,
            balance=Decimal("0.0000"),
            currency=settings.WALLET_DEFAULT_CURRENCY,
            status=WalletStatus.ACTIVE,
        )
        self._session.add(wallet)
        await self._session.flush()
        return wallet

    async def save(self, wallet: Wallet) -> Wallet:
        await self._session.flush()
        return wallet
