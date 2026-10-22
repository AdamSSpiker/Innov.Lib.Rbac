"""
RBAC-specific exceptions.

Minimal exception class for role-check failures. Task Tracker uses FastAPI's
built-in HTTPException directly in the role dependencies — this exception
class is provided for library consumers who want to catch RBAC failures
specifically vs. other HTTP exceptions, but the primary pattern is just
raising HTTPException(403) directly.
"""

from fastapi import HTTPException, status


class InsufficientRoleException(HTTPException):
    """
    Raised when a user lacks the required role for an operation.
    
    This is a convenience subclass of FastAPI's HTTPException with status_code
    fixed at 403 FORBIDDEN. Use when you want to distinguish RBAC failures from
    other HTTP errors in exception handlers.
    
    For most use cases, the built-in role dependencies (require_admin,
    require_supervisor, require_coordinator) already raise the appropriate
    HTTPException(403) automatically — you don't need to raise this manually.
    """

    def __init__(self, detail: str = "Insufficient role for this operation."):
        """
        Args:
            detail: Human-readable error message (default: generic denial)
        """
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
