class MatchingEngineError(Exception):
    """Base class for matching engine errors."""


class OrderNotFound(MatchingEngineError):
    """Raised when cancel/replace is called on a non-existent order."""
