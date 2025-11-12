"""Custom exceptions for Arena Improver."""


class MetaDataUnavailableError(Exception):
    """Raised when meta data cannot be fetched and no cache is available."""
    pass
