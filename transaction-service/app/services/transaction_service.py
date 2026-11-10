import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    DuplicateTransactionReferenceError,
    ReversalFailedError,
    TransactionNotFoundError,
    TransactionNotReversibleError,
)
from app.core.logging import get_logger
from app.core.metrics import transaction_reversal_total, transaction_transfer_total
from app.db.models.transaction import Transaction, TransactionStatus
from app.repositories.audit_repository import TransactionAuditRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import TransferRequest
from app.services.wallet_client import WalletServiceClient

logger = get_logger(__name__)

_REVERSAL_SUFFIX = "-REVERSAL"
_COMPENSATION_SUFFIX = "-COMPENSATION"


class TransactionService:
    """Orchestrates wallet-to-wallet transfers as a two-phase saga against
    wallet-service, with the local `transactions`/`transaction_audit`
    tables as the durable system of record for what was attempted and what
    happened. wallet-service's own per-wallet row lock plus ledger
    idempotency (see WalletServiceClient) is what actually guarantees a
    correct balance; this service's job is orchestration, auditability, and
    giving callers a single transaction resource to query and reverse.
    """

    def __init__(self, session: AsyncSession, wallet_client: WalletServiceClient | None = None) -> None:
        self._session = session
        self.transactions = TransactionRepository(session)
        self.audit = TransactionAuditRepository(session)
        self.wallet_client = wallet_client or WalletServiceClient()

    # ----------------------------------------------------------------
    # transfer_funds
    # ----------------------------------------------------------------

    async def transfer_funds(
        self, initiated_by_user_id: uuid.UUID, payload: TransferRequest
    ) -> Transaction:
        existing = await self.transactions.get_by_reference_id(payload.reference_id)
        if existing is not None:
            raise DuplicateTransactionReferenceError()

        transaction = await self.transactions.create(
            reference_id=payload.reference_id,
            from_wallet_id=payload.from_wallet_id,
            to_wallet_id=payload.to_wallet_id,
            amount=payload.amount,
            currency=payload.currency,
            initiated_by_user_id=initiated_by_user_id,
            status=TransactionStatus.PENDING,
        )
        await self.audit.log(
            transaction_id=transaction.id,
            action="TRANSFER_INITIATED",
            metadata={
                "from_wallet_id": str(payload.from_wallet_id),
                "to_wallet_id": str(payload.to_wallet_id),
                "amount": str(payload.amount),
                "currency": payload.currency,
            },
        )
        await self._session.commit()

        logger.info(
            "transfer_initiated",
            extra={"transaction_id": str(transaction.id), "reference_id": transaction.reference_id},
        )

        # --- Phase 1: debit the source wallet -----------------------------
        try:
            await self.wallet_client.debit(
                payload.from_wallet_id, payload.amount, payload.reference_id
            )
        except AppException as exc:
            await self._fail(transaction, action="DEBIT_FAILED", reason=str(exc.detail))
            transaction_transfer_total.labels(outcome="failed").inc()
            return transaction

        await self.audit.log(transaction_id=transaction.id, action="DEBIT_SUCCEEDED")
        await self._session.commit()

        # --- Phase 2: credit the destination wallet ------------------------
        try:
            await self.wallet_client.credit(
                payload.to_wallet_id, payload.amount, payload.reference_id
            )
        except AppException as exc:
            await self._compensate_failed_credit(transaction, original_error=str(exc.detail))
            transaction_transfer_total.labels(outcome="failed").inc()
            return transaction

        await self.audit.log(transaction_id=transaction.id, action="CREDIT_SUCCEEDED")
        await self.transactions.update_status(transaction, status=TransactionStatus.SUCCESS)
        await self.audit.log(transaction_id=transaction.id, action="TRANSFER_COMPLETED")
        await self._session.commit()

        transaction_transfer_total.labels(outcome="success").inc()
        logger.info(
            "transfer_completed",
            extra={"transaction_id": str(transaction.id), "reference_id": transaction.reference_id},
        )
        return transaction

    async def _compensate_failed_credit(self, transaction: Transaction, *, original_error: str) -> None:
        """The debit succeeded but the credit didn't — refund the source
        wallet so money isn't stranded mid-transfer, then mark the
        transaction FAILED either way."""
        await self.audit.log(
            transaction_id=transaction.id,
            action="CREDIT_FAILED",
            metadata={"error": original_error},
        )
        await self._session.commit()

        try:
            await self.wallet_client.credit(
                transaction.from_wallet_id,
                transaction.amount,
                f"{transaction.reference_id}{_COMPENSATION_SUFFIX}",
            )
            await self.audit.log(transaction_id=transaction.id, action="DEBIT_COMPENSATED")
            await self.transactions.update_status(
                transaction,
                status=TransactionStatus.FAILED,
                failure_reason=f"credit_failed_and_compensated: {original_error}",
            )
        except AppException as comp_exc:
            # The refund itself failed — this needs a human/alerting system,
            # not a silent retry, since money may now be stuck in limbo.
            await self.audit.log(
                transaction_id=transaction.id,
                action="COMPENSATION_FAILED",
                metadata={"error": str(comp_exc.detail)},
            )
            logger.error(
                "transfer_compensation_failed",
                extra={
                    "transaction_id": str(transaction.id),
                    "reference_id": transaction.reference_id,
                    "original_error": original_error,
                    "compensation_error": str(comp_exc.detail),
                },
            )
            await self.transactions.update_status(
                transaction,
                status=TransactionStatus.FAILED,
                failure_reason=(
                    f"credit_failed_compensation_failed: {original_error} / {comp_exc.detail}"
                ),
            )

        await self.audit.log(transaction_id=transaction.id, action="TRANSFER_FAILED")
        await self._session.commit()

    async def _fail(self, transaction: Transaction, *, action: str, reason: str) -> None:
        await self.audit.log(
            transaction_id=transaction.id, action=action, metadata={"error": reason}
        )
        await self.transactions.update_status(
            transaction, status=TransactionStatus.FAILED, failure_reason=reason
        )
        await self.audit.log(transaction_id=transaction.id, action="TRANSFER_FAILED")
        await self._session.commit()

        logger.warning(
            "transfer_failed",
            extra={"transaction_id": str(transaction.id), "reference_id": transaction.reference_id, "reason": reason},
        )

    # ----------------------------------------------------------------
    # reverse_transaction
    # ----------------------------------------------------------------

    async def reverse_transaction(self, transaction_id: uuid.UUID, *, reason: str | None) -> Transaction:
        transaction = await self.transactions.get_for_update_by_id(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError()
        if not transaction.is_reversible():
            raise TransactionNotReversibleError(
                f"Transaction status is '{transaction.status.value}'; only a SUCCESS "
                "transaction that has not already been reversed can be reversed"
            )

        reversal_reference = f"{transaction.reference_id}{_REVERSAL_SUFFIX}"

        await self.audit.log(
            transaction_id=transaction.id,
            action="REVERSAL_INITIATED",
            metadata={"reason": reason},
        )
        await self._session.commit()

        # --- Phase 1: claw back the funds from the destination wallet -----
        try:
            await self.wallet_client.debit(
                transaction.to_wallet_id, transaction.amount, reversal_reference
            )
        except AppException as exc:
            await self.audit.log(
                transaction_id=transaction.id,
                action="REVERSAL_FAILED",
                metadata={"error": str(exc.detail)},
            )
            await self._session.commit()
            transaction_reversal_total.labels(outcome="failed").inc()
            raise ReversalFailedError(
                f"Could not reclaim funds from destination wallet: {exc.detail}"
            ) from exc

        await self.audit.log(transaction_id=transaction.id, action="REVERSAL_DEBIT_SUCCEEDED")
        await self._session.commit()

        # --- Phase 2: return the funds to the original source wallet ------
        try:
            await self.wallet_client.credit(
                transaction.from_wallet_id, transaction.amount, reversal_reference
            )
        except AppException as exc:
            # Funds were pulled from the destination but not yet returned to
            # the source — flag loudly for manual reconciliation rather than
            # silently leaving the transaction in an ambiguous state.
            await self.audit.log(
                transaction_id=transaction.id,
                action="REVERSAL_CREDIT_FAILED",
                metadata={"error": str(exc.detail)},
            )
            logger.error(
                "reversal_credit_failed_requires_manual_reconciliation",
                extra={"transaction_id": str(transaction.id), "reference_id": transaction.reference_id},
            )
            await self._session.commit()
            transaction_reversal_total.labels(outcome="failed").inc()
            raise ReversalFailedError(
                f"Funds were reclaimed but could not be returned to the source wallet: {exc.detail}"
            ) from exc

        await self.transactions.update_status(transaction, status=TransactionStatus.REVERSED)
        await self.audit.log(
            transaction_id=transaction.id,
            action="REVERSAL_COMPLETED",
            metadata={"reason": reason},
        )
        await self._session.commit()

        transaction_reversal_total.labels(outcome="success").inc()
        logger.info(
            "reversal_completed",
            extra={"transaction_id": str(transaction.id), "reference_id": transaction.reference_id},
        )
        return transaction

    # ----------------------------------------------------------------
    # Queries
    # ----------------------------------------------------------------

    async def get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        transaction = await self.transactions.get_by_id(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError()
        return transaction

    async def list_transactions(
        self,
        *,
        status: TransactionStatus | None = None,
        wallet_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Transaction], int]:
        return await self.transactions.list_paginated(
            status=status, wallet_id=wallet_id, page=page, page_size=page_size
        )
