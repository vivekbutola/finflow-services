class AppException(Exception):
    """Base class for all wallet-service domain exceptions."""

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


# --- Wallet lifecycle errors -------------------------------------------------

class WalletNotFoundError(AppException):
    """No wallet exists for this user."""

    status_code = 404
    error_type = "wallet_not_found"


class WalletAlreadyExistsError(AppException):
    """A wallet already exists for this user; only one wallet per user is permitted."""

    status_code = 409
    error_type = "wallet_already_exists"


class WalletFrozenError(AppException):
    """The wallet is frozen and cannot accept credit or debit operations."""

    status_code = 400
    error_type = "wallet_frozen"


class WalletClosedError(AppException):
    """The wallet is closed and no further operations are permitted."""

    status_code = 400
    error_type = "wallet_closed"


class WalletNotFrozenError(AppException):
    """The wallet is not currently frozen, so it cannot be unfrozen."""

    status_code = 400
    error_type = "wallet_not_frozen"


class WalletCloseBalanceNotZeroError(AppException):
    """The wallet balance must be zero before it can be closed."""

    status_code = 400
    error_type = "wallet_balance_not_zero"


# --- Money movement errors ---------------------------------------------------

class InsufficientBalanceError(AppException):
    """The wallet does not have sufficient available balance for this debit."""

    status_code = 400
    error_type = "insufficient_balance"


class InvalidAmountError(AppException):
    """The supplied amount is not a valid positive monetary value."""

    status_code = 422
    error_type = "invalid_amount"


class ConcurrencyConflictError(AppException):
    """The wallet was modified concurrently; the request should be retried."""

    status_code = 409
    error_type = "concurrency_conflict"
