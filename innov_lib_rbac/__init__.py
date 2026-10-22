"""
Innov.Lib.Rbac - Role-Based Access Control library for FastAPI applications.

Extracted from RPA Task Tracker backend and adapted for reusable library distribution.
Provides three-tier role hierarchy (Admin > Supervisor > Coordinator) with FastAPI
dependency injection for endpoint protection.

Quick Start:
    from fastapi import FastAPI, Depends
    from innov_lib_rbac import require_admin, require_coordinator, RbacRoles
    from innov_lib_rbac.dependencies import get_current_user
    
    app = FastAPI()
    
    # Override the get_current_user dependency with your auth implementation
    from myapp.auth import my_get_current_user
    app.dependency_overrides[get_current_user] = my_get_current_user
    
    @app.get("/admin-only")
    async def admin_endpoint(user: dict = Depends(require_admin)):
        return {"message": "Admin access granted", "user": user["email"]}
    
    @app.get("/team")
    async def team_endpoint(user: dict = Depends(require_coordinator)):
        # Admits Coordinator, Supervisor, or Admin
        return {"message": f"Welcome {user['name']}"}

Core Exports:
    - RbacRoles: Role constants (ADMIN, SUPERVISOR, COORDINATOR)
    - require_admin: Dependency that admits Admin only
    - require_supervisor: Dependency that admits Supervisor or Admin
    - require_coordinator: Dependency that admits Coordinator or higher
    - check_role: Helper for manual role checks in endpoint logic
    - InsufficientRoleException: 403 exception for role check failures

For detailed documentation, see: docs/IMPLEMENTATION_GUIDE.md
"""

__version__ = "1.0.0"

from .dependencies import (
    check_role,
    get_current_user,
    require_admin,
    require_coordinator,
    require_supervisor,
)
from .exceptions import InsufficientRoleException
from .roles import ROLE_ADMIN, ROLE_COORDINATOR, ROLE_SUPERVISOR, RbacRoles

__all__ = [
    # Role constants
    "RbacRoles",
    "ROLE_ADMIN",
    "ROLE_SUPERVISOR",
    "ROLE_COORDINATOR",
    # FastAPI dependencies
    "require_admin",
    "require_supervisor",
    "require_coordinator",
    "get_current_user",
    # Helpers
    "check_role",
    # Exceptions
    "InsufficientRoleException",
]
