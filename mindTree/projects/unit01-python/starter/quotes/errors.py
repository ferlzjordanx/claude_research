"""Exception hierarchy. Callers catch the narrowest type they handle."""


class QuoteError(Exception):
    """Base class for all errors raised by this package."""


class TransientSupplierError(QuoteError):
    """Temporary failure (network blip, 503). Safe to retry."""


class SupplierTimeoutError(TransientSupplierError):
    """The supplier did not answer within the allowed time."""


class PermanentSupplierError(QuoteError):
    """Failure that will not go away on retry (bad SKU, auth error)."""


class InvalidSkuError(PermanentSupplierError):
    """The supplier does not recognise the SKU."""
