"""PEARatings data API client for college baseball and softball.

    from pearatings import Pear
    pear = Pear()                      # reads PEAR_API_KEY
    pear.ratings()                     # D1 baseball ratings as a DataFrame
"""
__version__ = "1.0.1"

from .client import Pear  # noqa: E402
from .errors import (APIError, AuthenticationError, InvalidRequestError, NotFoundError, PearError,  # noqa: E402
                     RateLimitError, TierError)

__all__ = ["Pear", "PearError", "AuthenticationError", "NotFoundError", "InvalidRequestError", "RateLimitError",
           "TierError", "APIError", "__version__"]
