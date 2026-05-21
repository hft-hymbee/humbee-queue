"""
Core Exceptions
===============
Custom exception classes
"""

class ProviderError(Exception):
    """Base class for all provider-related errors."""
    pass

class Provider5xxError(ProviderError):
    """Raised when the provider API returns a 5xx server error."""
    pass

class RateLimitError(ProviderError):
    """Raised when the provider API returns a 429 rate limit error."""
    pass

class ProviderFailedError(ProviderError):
    """Raised when the provider indicates a failure in processing the message."""
    pass
