"""Errors raised by the PEARatings client. Catch `PearError` to handle all of them."""


class PearError(Exception):
    """Base class. `status_code` is the HTTP status (None when no request was made)."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(PearError):
    """No API key, or the API rejected it (HTTP 401)."""


class NotFoundError(PearError):
    """Unknown team, player, season or division, or no data for it yet (HTTP 404)."""


class InvalidRequestError(PearError):
    """The API rejected the parameters (HTTP 400 / 422)."""


class RateLimitError(PearError):
    """Too many requests in a short time (HTTP 429). Wait a few seconds and retry."""


class APIError(PearError):
    """Any other error from the API (HTTP 5xx, or data not available right now, e.g. 503 out of season)."""
