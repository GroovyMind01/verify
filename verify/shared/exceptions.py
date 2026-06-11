"""Shared exception hierarchy."""


class VerifyError(Exception):
    """Base exception for all Verify errors."""

    message: str

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class NotFoundError(VerifyError):
    """Raised when a requested entity does not exist."""


class ValidationError(VerifyError):
    """Raised when input data fails validation."""


class RequirementImportError(VerifyError):
    """Raised when importing requirements fails."""


class CampaignError(VerifyError):
    """Raised for invalid campaign operations."""
