class AppException(Exception):
    """Base class for all auth-service domain exceptions."""

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.__doc__ or "An error occurred"
        super().__init__(self.detail)


class InvalidCredentialsError(AppException):
    """Email or password is incorrect."""

    status_code = 401
    error_type = "invalid_credentials"


class AccountLockedError(AppException):
    """Account is temporarily locked due to repeated failed login attempts."""

    status_code = 423
    error_type = "account_locked"


class AccountNotActiveError(AppException):
    """Account is suspended, deleted, or otherwise not active."""

    status_code = 403
    error_type = "account_not_active"


class UserAlreadyExistsError(AppException):
    """A user with this email already exists."""

    status_code = 409
    error_type = "user_already_exists"


class UserNotFoundError(AppException):
    """No matching user was found."""

    status_code = 404
    error_type = "user_not_found"


class InvalidTokenError(AppException):
    """The provided token is invalid, malformed, or has an unexpected signature."""

    status_code = 401
    error_type = "invalid_token"


class TokenExpiredError(AppException):
    """The provided token has expired."""

    status_code = 401
    error_type = "token_expired"


class RefreshTokenReusedError(AppException):
    """A previously-rotated refresh token was reused; token family has been revoked."""

    status_code = 401
    error_type = "refresh_token_reused"


class WeakPasswordError(AppException):
    """Password does not meet minimum security requirements."""

    status_code = 422
    error_type = "weak_password"
