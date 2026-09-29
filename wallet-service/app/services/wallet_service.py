import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConcurrencyConflictError,
    InsufficientBalanceError,
    WalletAlreadyExistsError,
    WalletCloseBalanceNotZeroError,
    WalletClosedError,
    WalletFrozenError,
    WalletNotFoundError,
    WalletNotFrozenError,
)
from app.core.logging import get_logger
from app.core.metrics import (
    wallet_balance_operations_total,
    wallet_credit_total,
    wallet_debit_total,
    wallet_freeze_total,
    wallet_unfreeze_total,
)
from app.db.models.wallet import Wallet, WalletStatus
from app.db.models.wallet_ledger import LedgerEntryType, WalletLedger
from app.repositories.wallet_ledger_repository import WalletLedgerRepository
from app.repositories.wallet_repository import WalletRepository

logger = get_logger(__name__)


class WalletService:
    """Orchestrates wallet lifecycle and money-movement use-cases. Every
    balance mutation runs inside a single DB transaction, guarded by a
    pessimistic row lock (`SELECT ... FOR UPDATE`) plus the ORM's optimistic
    `version` column, and is recorded as an immutable wallet_ledger entry.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.wallets = WalletRepository(session)
        self.ledger = WalletLedgerRepository(session)

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------

    async def get_wallet(self, user_id: uuid.UUID) -> Wallet:
        wallet = await self.wallets.get_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        return wallet

    async def create_wallet(self, user_id: uuid.UUID) -> Wallet:
        existing = await self.wallets.get_by_user_id(user_id)
        if existing is not None:
            raise WalletAlreadyExistsError()

        # The pre-check above is inherently a check-then-act race: two
        # concurrent create requests for the same user can both observe
        # "no wallet yet" before either commits. The unique index on
        # wallets.user_id is the real source of truth that prevents two
        # wallets ever existing; here we translate the resulting
        # IntegrityError into the same domain error the pre-check raises,
        # instead of letting it surface as an unhandled 500.
        try:
            wallet = await self.wallets.create(user_id=user_id)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if "ux_wallets_user_id" in str(exc.orig):
                raise WalletAlreadyExistsError(
                    "A wallet already exists for this user"
                ) from exc
            raise

        logger.info("wallet_created", extra={"user_id": str(user_id), "wallet_id": wallet.wallet_id})
        return wallet

    async def freeze_wallet(self, user_id: uuid.UUID) -> Wallet:
        wallet = await self.wallets.get_for_update_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        if wallet.status == WalletStatus.CLOSED:
            raise WalletClosedError()

        wallet.status = WalletStatus.FROZEN
        await self.wallets.save(wallet)
        await self._session.commit()

        wallet_freeze_total.inc()
        logger.info("wallet_frozen", extra={"user_id": str(user_id), "wallet_id": wallet.wallet_id})
        return wallet

    async def unfreeze_wallet(self, user_id: uuid.UUID) -> Wallet:
        wallet = await self.wallets.get_for_update_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        if wallet.status == WalletStatus.CLOSED:
            raise WalletClosedError()
        if wallet.status != WalletStatus.FROZEN:
            raise WalletNotFrozenError()

        wallet.status = WalletStatus.ACTIVE
        await self.wallets.save(wallet)
        await self._session.commit()

        wallet_unfreeze_total.inc()
        logger.info("wallet_unfrozen", extra={"user_id": str(user_id), "wallet_id": wallet.wallet_id})
        return wallet

    async def close_wallet(self, user_id: uuid.UUID) -> Wallet:
        wallet = await self.wallets.get_for_update_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        if wallet.status == WalletStatus.CLOSED:
            raise WalletClosedError()
        if wallet.status == WalletStatus.FROZEN:
            raise WalletFrozenError("A frozen wallet cannot be closed; unfreeze it first")
        if wallet.balance != Decimal("0.0000"):
            raise WalletCloseBalanceNotZeroError()

        wallet.status = WalletStatus.CLOSED
        await self.wallets.save(wallet)
        await self._session.commit()

        logger.info("wallet_closed", extra={"user_id": str(user_id), "wallet_id": wallet.wallet_id})
        return wallet

    # ----------------------------------------------------------------
    # Money movement
    # ----------------------------------------------------------------

    async def credit(
        self, user_id: uuid.UUID, *, amount: Decimal, reference_id: str
    ) -> tuple[Wallet, WalletLedger]:
        try:
            wallet = await self.wallets.get_for_update_by_user_id(user_id)
            if wallet is None:
                raise WalletNotFoundError()

            self._assert_operable(wallet, operation="credit")

            existing_entry = await self.ledger.get_by_wallet_and_reference(wallet.id, reference_id)
            if existing_entry is not None:
                # Idempotent replay: the same reference_id was already
                # processed, so we return the prior result unchanged rather
                # than crediting the wallet a second time. No writes have
                # occurred yet, so there is nothing to roll back — the only
                # statements issued so far are the SELECT ... FOR UPDATE and
                # this lookup. Explicitly rolling back here would expire the
                # `wallet`/`existing_entry` ORM objects; since this is an
                # AsyncSession, any subsequent synchronous attribute access
                # (e.g. while building the response) would then raise
                # MissingGreenlet. The pending (read-only) transaction is
                # safely discarded by get_db()'s session.close() once the
                # request completes.
                logger.info(
                    "wallet_credit_idempotent_replay",
                    extra={"wallet_id": wallet.wallet_id, "reference_id": reference_id},
                )
                return wallet, existing_entry

            balance_before = wallet.balance
            balance_after = balance_before + amount
            wallet.balance = balance_after

            await self.wallets.save(wallet)
            entry = await self.ledger.create(
                wallet_id=wallet.id,
                entry_type=LedgerEntryType.CREDIT,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=reference_id,
            )

            await self._session.commit()
        except StaleDataError as exc:
            await self._session.rollback()
            raise ConcurrencyConflictError(
                "Wallet was modified concurrently; please retry the request"
            ) from exc

        wallet_credit_total.inc()
        wallet_balance_operations_total.labels(operation="credit", outcome="success").inc()
        logger.info(
            "wallet_credited",
            extra={"wallet_id": wallet.wallet_id, "amount": str(amount), "reference_id": reference_id},
        )
        return wallet, entry

    async def debit(
        self, user_id: uuid.UUID, *, amount: Decimal, reference_id: str
    ) -> tuple[Wallet, WalletLedger]:
        try:
            wallet = await self.wallets.get_for_update_by_user_id(user_id)
            if wallet is None:
                raise WalletNotFoundError()

            self._assert_operable(wallet, operation="debit")

            existing_entry = await self.ledger.get_by_wallet_and_reference(wallet.id, reference_id)
            if existing_entry is not None:
                # See the identical comment in credit() above: no writes
                # have occurred yet, so we must not roll back here — doing
                # so would expire these ORM objects and crash response
                # serialization with MissingGreenlet.
                logger.info(
                    "wallet_debit_idempotent_replay",
                    extra={"wallet_id": wallet.wallet_id, "reference_id": reference_id},
                )
                return wallet, existing_entry

            if wallet.balance < amount:
                wallet_balance_operations_total.labels(operation="debit", outcome="insufficient_funds").inc()
                raise InsufficientBalanceError(
                    f"Wallet balance {wallet.balance} is insufficient for a debit of {amount}"
                )

            balance_before = wallet.balance
            balance_after = balance_before - amount
            wallet.balance = balance_after

            await self.wallets.save(wallet)
            entry = await self.ledger.create(
                wallet_id=wallet.id,
                entry_type=LedgerEntryType.DEBIT,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=reference_id,
            )

            await self._session.commit()
        except StaleDataError as exc:
            await self._session.rollback()
            raise ConcurrencyConflictError(
                "Wallet was modified concurrently; please retry the request"
            ) from exc

        wallet_debit_total.inc()
        wallet_balance_operations_total.labels(operation="debit", outcome="success").inc()
        logger.info(
            "wallet_debited",
            extra={"wallet_id": wallet.wallet_id, "amount": str(amount), "reference_id": reference_id},
        )
        return wallet, entry

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _assert_operable(wallet: Wallet, *, operation: str) -> None:
        if wallet.status == WalletStatus.CLOSED:
            wallet_balance_operations_total.labels(operation=operation, outcome="wallet_closed").inc()
            raise WalletClosedError()
        if wallet.status == WalletStatus.FROZEN:
            wallet_balance_operations_total.labels(operation=operation, outcome="wallet_frozen").inc()
            raise WalletFrozenError()
