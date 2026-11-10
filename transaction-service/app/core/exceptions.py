class AppException(Exception):
    """Base class for all transaction-service domain exceptions."""

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.__doc__ or "An error occurred"
        super().__init__(self.detail)


# --- Authentication / token errors -----------------------------------------

class InvalidTokenError(AppException):
    """The provided access token is invalid, malformed, or has an unexpected signature."""

    status_code = 401
    error_type = "invalid_token"


class TokenExpiredError(AppException):
    """The provided access token has expired."""

    status_code = 401
    error_type = "token_expired"


# --- Transfer validation errors ---------------------------------------------

class InvalidAmountError(AppException):
    """The supplied amount is not a valid positive monetary value."""

    status_code = 422
    error_type = "invalid_amount"


class InvalidCurrencyError(AppException):
    """The supplied currency is not a supported ISO-4217 currency code."""

    status_code = 422
    error_type = "invalid_currency"


class SameWalletTransferError(AppException):
    """The source and destination wallet must be different."""

    status_code = 422
    error_type = "same_wallet_transfer"


class DuplicateTransactionReferenceError(AppException):
    """A transaction with this reference_id already exists."""

    status_code = 409
    error_type = "duplicate_transaction_reference"


# --- Transaction lifecycle errors --------------------------------------------

class TransactionNotFoundError(AppException):
    """No transaction exists with this id."""

    status_code = 404
    error_type = "transaction_not_found"


class TransactionNotReversibleError(AppException):
    """Only a SUCCESS transaction that has not already been reversed can be reversed."""

    status_code = 409
    error_type = "transaction_not_reversible"


class ReversalFailedError(AppException):
    """The reversal could not be completed against the destination wallet."""

    status_code = 400
    error_type = "reversal_failed"


# --- Downstream wallet-service errors ---------------------------------------

class WalletNotFoundError(AppException):
    """The referenced wallet does not exist."""

    status_code = 404
    error_type = "wallet_not_found"


class WalletNotOperableError(AppException):
    """The referenced wallet is frozen or closed and cannot accept this operation."""

    status_code = 400
    error_type = "wallet_not_operable"


class InsufficientFundsError(AppException):
    """The source wallet does not have sufficient balance for this transfer."""

    status_code = 400
    error_type = "insufficient_funds"


class WalletServiceUnavailableError(AppException):
    """wallet-service could not be reached or did not respond in time."""

    status_code = 503
    error_type = "wallet_service_unavailable"
