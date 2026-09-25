class FinGuardError(Exception):
    """Base domain exception."""


class ModelNotLoadedError(FinGuardError):
    """Raised when scoring is attempted before the model is ready."""


class TransactionNotFoundError(FinGuardError):
    """Raised when a requested transaction does not exist."""