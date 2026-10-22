"""
FastAPI dependency functions for role-based access control.

Extracted from RPA Task Tracker backend (D:/repos/RPA.TaskTracker.UX/backend/app/core/roles.py)
and adapted for library use. Each dependency admits users with the required role or any
higher-privilege role per the hierarchy: Admin > Supervisor > Coordinator.

These dependencies expect:
  - A `get_current_user` dependency that returns dict[str, Any] with a "roles" key
  - The "roles" value is a list of role strings (e.g., ["Admin", "Supervisor"])
  
Applications using this library must provide their own get_current_user implementation
and inject it via dependency_overrides if the name differs.
"""

from typing import Any

from fastapi import Depends, HTTPException, status

from .roles import ROLE_ADMIN, ROLE_COORDINATOR, ROLE_SUPERVISOR, RbacRoles


# Placeholder for get_current_user — applications MUST override this dependency
# with their own authentication implementation
def get_current_user() -> dict[str, Any]:
    """
    Placeholder dependency for current user authentication.
    
    Applications MUST override this using FastAPI's dependency_overrides:
    
        from innov_lib_rbac.dependencies import get_current_user
        from myapp.auth import my_get_current_user
        
        app.dependency_overrides[get_current_user] = my_get_current_user
    
    Expected return structure:
        {
            "email": "user@example.com",
            "name": "User Name",
            "roles": ["Coordinator", "Supervisor"]  # List of role strings
        }
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "get_current_user dependency not configured. "
            "Override innov_lib_rbac.dependencies.get_current_user with your auth implementation."
        ),
    )


def require_coordinator(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    FastAPI dependency: admits Coordinator, Supervisor, or Admin.
    
    This is the base authenticated-user policy — nearly every protected endpoint
    should use this as the minimum requirement.
    
    Raises:
        HTTPException (403): If user lacks Coordinator role or higher
        
    Returns:
        The user dict unchanged (for chaining with other dependencies)
    """
    if not RbacRoles.check_role(user, ROLE_COORDINATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Coordinator role required.",
        )
    return user


def require_supervisor(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    FastAPI dependency: admits Supervisor or Admin.
    
    Use for endpoints that manage team-level resources or perform supervisory actions.
    
    Raises:
        HTTPException (403): If user lacks Supervisor role or higher
        
    Returns:
        The user dict unchanged (for chaining with other dependencies)
    """
    if not RbacRoles.check_role(user, ROLE_SUPERVISOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor role required.",
        )
    return user


def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    FastAPI dependency: admits Admin only.
    
    Use for endpoints that modify system-wide configuration, manage users/roles,
    or perform other administrative actions.
    
    Raises:
        HTTPException (403): If user lacks Admin role
        
    Returns:
        The user dict unchanged (for chaining with other dependencies)
    """
    if not RbacRoles.check_role(user, ROLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return user


def check_role(user: dict[str, Any], required_role: str) -> bool:
    """
    Helper function: check if user satisfies a role requirement.
    
    This is a convenience wrapper around RbacRoles.check_role() for direct use
    in endpoint logic (not as a FastAPI dependency).
    
    Args:
        user: User dict with "roles" key
        required_role: One of ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_COORDINATOR
        
    Returns:
        True if user has required role or higher, False otherwise
        
    Example:
        @router.post("/conditional-action")
        async def conditional(user: dict = Depends(require_coordinator)):
            if check_role(user, ROLE_ADMIN):
                # Admin-only logic
                pass
            else:
                # Regular coordinator/supervisor logic
                pass
    """
    return RbacRoles.check_role(user, required_role)
