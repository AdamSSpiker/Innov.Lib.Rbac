"""
Minimal FastAPI example demonstrating innov-lib-rbac usage.

This example shows:
- JWT authentication setup (mocked for demo purposes)
- Three-tier role hierarchy enforcement (Admin > Supervisor > Coordinator)
- Public, protected, and admin-only endpoints
- Router-level dependency injection
- Role-based access control in action

Run:
    uvicorn fastapi_app:app --reload

Test endpoints:
    curl http://localhost:8000/public
    curl -H "Authorization: Bearer coordinator_token" http://localhost:8000/supervisor
    curl -H "Authorization: Bearer admin_token" http://localhost:8000/admin
"""

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from innov_lib_rbac import (
    RbacRoles,
    require_admin,
    require_coordinator,
    require_supervisor,
)
from innov_lib_rbac.dependencies import get_current_user

# ============================================================================
# Mock JWT Authentication (Replace with real JWT validation in production)
# ============================================================================

# Mock user database keyed by token
MOCK_USERS = {
    "coordinator_token": {
        "email": "coordinator@example.com",
        "name": "Coordinator User",
        "roles": [RbacRoles.COORDINATOR],
    },
    "supervisor_token": {
        "email": "supervisor@example.com",
        "name": "Supervisor User",
        "roles": [RbacRoles.SUPERVISOR, RbacRoles.COORDINATOR],
    },
    "admin_token": {
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": [RbacRoles.ADMIN, RbacRoles.SUPERVISOR, RbacRoles.COORDINATOR],
    },
}


def mock_get_current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
    """
    Mock authentication dependency for demonstration purposes.
    
    In production, replace this with real JWT validation using python-jose
    or equivalent. See docs/IMPLEMENTATION_GUIDE.md for production patterns.
    
    Expects:
        Authorization: Bearer <token>
        
    Returns:
        User dict with email, name, and roles list
        
    Raises:
        HTTPException (401): If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Strip "Bearer "

    user = MOCK_USERS.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="Innov.Lib.Rbac Example",
    description="Demonstration of role-based access control using innov-lib-rbac",
    version="1.0.0",
)

# Override the library's placeholder get_current_user with our mock implementation
app.dependency_overrides[get_current_user] = mock_get_current_user


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================


@app.get("/public")
async def public_endpoint():
    """
    Public endpoint accessible without authentication.
    
    No Depends() on any RBAC dependency — completely open.
    """
    return {
        "message": "This endpoint is public",
        "info": "No authentication required",
    }


@app.get("/")
async def root():
    """Root endpoint with usage instructions."""
    return {
        "message": "Innov.Lib.Rbac FastAPI Example",
        "endpoints": {
            "/public": "Public access (no auth)",
            "/supervisor": "Requires Supervisor or Admin role",
            "/admin": "Requires Admin role only",
            "/me": "Returns current user info (requires Coordinator+)",
        },
        "test_tokens": {
            "coordinator": "coordinator_token",
            "supervisor": "supervisor_token",
            "admin": "admin_token",
        },
        "example": 'curl -H "Authorization: Bearer admin_token" http://localhost:8000/admin',
    }


# ============================================================================
# Protected Endpoints (Role-Based Access Control)
# ============================================================================


@app.get("/me")
async def current_user_info(user: dict[str, Any] = Depends(require_coordinator)):
    """
    Returns current user information.
    
    Requires: Coordinator role or higher (Coordinator, Supervisor, or Admin)
    
    This demonstrates the base authentication policy — any authenticated user
    with at least Coordinator role can access this endpoint.
    """
    return {
        "email": user["email"],
        "name": user["name"],
        "roles": user["roles"],
        "message": f"Authenticated as {user['name']}",
    }


@app.get("/supervisor")
async def supervisor_endpoint(user: dict[str, Any] = Depends(require_supervisor)):
    """
    Supervisor-level protected endpoint.
    
    Requires: Supervisor or Admin role
    
    This demonstrates role hierarchy in action:
    - coordinator_token: 403 Forbidden (insufficient role)
    - supervisor_token: 200 OK
    - admin_token: 200 OK (Admin inherits Supervisor privileges)
    """
    return {
        "message": "Supervisor access granted",
        "user": user["email"],
        "roles": user["roles"],
        "info": "This endpoint admits Supervisor or Admin roles",
    }


@app.get("/admin")
async def admin_endpoint(user: dict[str, Any] = Depends(require_admin)):
    """
    Admin-only protected endpoint.
    
    Requires: Admin role
    
    This demonstrates strict role enforcement:
    - coordinator_token: 403 Forbidden
    - supervisor_token: 403 Forbidden
    - admin_token: 200 OK
    """
    return {
        "message": "Admin access granted",
        "user": user["email"],
        "roles": user["roles"],
        "info": "This endpoint admits Admin role only",
    }


# ============================================================================
# Router-Level Protection Example
# ============================================================================
#
# For real applications with many endpoints, apply dependencies at router level:
#
#   from fastapi import APIRouter
#
#   admin_router = APIRouter(
#       prefix="/admin",
#       dependencies=[Depends(require_admin)]  # All routes require Admin
#   )
#
#   @admin_router.get("/users")
#   async def list_users():
#       return {"users": [...]}
#
#   @admin_router.post("/users")
#   async def create_user():
#       return {"created": True}
#
#   app.include_router(admin_router)
#
# See docs/IMPLEMENTATION_GUIDE.md for complete patterns.
# ============================================================================


if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI example app...")
    print("Visit http://localhost:8000 for endpoint documentation")
    print("\nTest tokens:")
    print("  Coordinator: coordinator_token")
    print("  Supervisor:  supervisor_token")
    print("  Admin:       admin_token")
    print("\nExample request:")
    print('  curl -H "Authorization: Bearer admin_token" http://localhost:8000/admin')
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
