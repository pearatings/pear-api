"""Errors raised by the PEARatings client. Catch `PearError` to handle all of them."""


class PearError(Exception):
    """Base class. `status_code` is the HTTP status (None when no request was made)."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(PearError):
    """No API key, the API doesn't know it (HTTP 401), or it is no longer active: revoked or the subscription
    lapsed (HTTP 403)."""


class TierError(PearError):
    """The endpoint needs a higher tier than your key's (HTTP 403). `required_tier` is the lowest tier that reaches
    it ("plus", "pro" or "max"); upgrade with `Pear().billing_portal()`."""

    def __init__(self, message, status_code=None, required_tier=None):
        super().__init__(message, status_code)
        self.required_tier = required_tier


class NotFoundError(PearError):
    """Unknown team, player, season or division, or no data for it yet (HTTP 404)."""


class InvalidRequestError(PearError):
    """The API rejected the parameters (HTTP 400 / 422)."""


class RateLimitError(PearError):
    """Over your tier's per-minute or monthly limit (HTTP 429). `retry_after` is the seconds to wait (or None)."""

    def __init__(self, message, status_code=None, retry_after=None):
        super().__init__(message, status_code)
        self.retry_after = retry_after


class APIError(PearError):
    """Any other error from the API (HTTP 5xx, or data not available right now, e.g. 503 out of season)."""
