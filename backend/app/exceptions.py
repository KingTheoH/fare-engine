"""
exceptions.py — Custom exception hierarchy.

All service-level exceptions are defined here. API routes catch these
and convert them to appropriate HTTP responses.
"""


class FareEngineError(Exception):
    """Base exception for all fare engine errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(FareEngineError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class ValidationError(FareEngineError):
    """Input validation failed."""
    pass


class DuplicateError(FareEngineError):
    """Attempted to create a duplicate resource."""

    def __init__(self, resource: str, field: str, value: str):
        self.resource = resource
        self.field = field
        self.value = value
        super().__init__(f"{resource} with {field}='{value}' already exists")


class AuthenticationError(FareEngineError):
    """API key authentication failed."""

    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message)


class LifecycleError(FareEngineError):
    """Invalid lifecycle state transition."""

    def __init__(self, current_state: str, target_state: str):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Cannot transition from '{current_state}' to '{target_state}'"
        )
