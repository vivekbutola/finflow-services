class AppException(Exception):
    """Base class for all user-service domain exceptions."""

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


class MissingCredentialsError(AppException):
    """No credentials were supplied on a request that requires authentication."""

    status_code = 401
    error_type = "missing_credentials"


# --- Profile errors ----------------------------------------------------------

class UserProfileNotFoundError(AppException):
    """No user profile exists for this account."""

    status_code = 404
    error_type = "user_profile_not_found"


# --- Address errors ------------------------------------------------------

class AddressNotFoundError(AppException):
    """No matching address was found for this user."""

    status_code = 404
    error_type = "address_not_found"


class MaxAddressesExceededError(AppException):
    """The maximum number of saved addresses has been reached."""

    status_code = 422
    error_type = "max_addresses_exceeded"


# --- KYC errors ------------------------------------------------------------

class KycProfileNotFoundError(AppException):
    """No KYC profile has been submitted for this user."""

    status_code = 404
    error_type = "kyc_profile_not_found"


class KycAlreadySubmittedError(AppException):
    """A KYC profile has already been submitted for this user."""

    status_code = 409
    error_type = "kyc_already_submitted"


class KycImmutableStateError(AppException):
    """The KYC profile cannot be modified in its current verification state."""

    status_code = 409
    error_type = "kyc_immutable_state"


# --- Preferences errors ---------------------------------------------------

class PreferencesNotFoundError(AppException):
    """No preferences record exists for this user."""

    status_code = 404
    error_type = "preferences_not_found"


class NotificationPreferencesNotFoundError(AppException):
    """No notification preferences record exists for this user."""

    status_code = 404
    error_type = "notification_preferences_not_found"


# --- Generic validation / access ------------------------------------------

class ValidationError(AppException):
    """The request payload failed a business validation rule."""

    status_code = 422
    error_type = "validation_error"


class ForbiddenError(AppException):
    """The authenticated user is not permitted to perform this action."""

    status_code = 403
    error_type = "forbidden"
