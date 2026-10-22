# Innov.Lib.Rbac

Modular Role-Based Access Control (RBAC) library for FastAPI applications with Azure AD/Entra ID integration.

## Overview

This library provides a lightweight, reusable RBAC pattern for FastAPI applications authenticating with Azure AD/Entra ID. It eliminates the need to reimplement role-based authorization logic in every project by providing FastAPI dependencies, role hierarchy validation, and declarative authorization that work seamlessly with Entra JWT tokens.

**Designed for:** Internal DCLI Python applications requiring role-based authorization with a hierarchical access model (Admin > Supervisor > Coordinator).

## Key Features

- **FastAPI Dependencies** — Drop-in `require_admin`, `require_supervisor`, `require_coordinator` dependencies for route protection
- **Role Hierarchy Enforcement** — Three-tier hierarchy (Admin > Supervisor > Coordinator) with set-based access control
- **Minimal Integration** — Override one function (`get_current_user`) and you're done
- **Zero Boilerplate** — No middleware registration, no policy configuration — just add dependencies to your routes
- **Flexible User Model** — Works with any user dict/object that has a `roles` field (list of role strings)
- **Comprehensive Test Coverage** — 26 unit tests covering role hierarchy, dependencies, exceptions, and edge cases

## Quick Start

### Install from GitHub

Until published to PyPI:

```bash
pip install git+https://github.com/dcli-com/Innov.Lib.Rbac.git
```

Or for editable/development install:

```bash
git clone https://github.com/dcli-com/Innov.Lib.Rbac.git
cd Innov.Lib.Rbac
pip install -e .
```

### Basic Usage

**Step 1: Override `get_current_user` with your authentication logic**

```python
from fastapi import FastAPI, Depends
from innov_lib_rbac import get_current_user, require_admin, require_supervisor, require_coordinator

app = FastAPI()

# Your authentication function that returns a user dict with "roles" list
async def my_auth_function():
    # Your logic here: decode JWT, query database, etc.
    return {
        "email": "user@dcli.com",
        "name": "John Doe",
        "roles": ["Coordinator", "Supervisor"]  # Must be a list
    }

# Override the library's placeholder with your auth
app.dependency_overrides[get_current_user] = my_auth_function
```

**Step 2: Protect routes with role dependencies**

```python
from innov_lib_rbac import require_admin, require_supervisor, require_coordinator

@app.get("/api/tasks/mine")
async def get_my_tasks(user=Depends(require_coordinator)):
    # Accessible by Coordinator, Supervisor, or Admin
    return {"tasks": [...]}

@app.get("/api/tasks/all")
async def get_all_tasks(user=Depends(require_supervisor)):
    # Accessible by Supervisor or Admin only
    return {"tasks": [...]}

@app.post("/api/admin/bulk-approve")
async def bulk_approve(user=Depends(require_admin)):
    # Accessible by Admin only
    return {"success": True}
```

That's it. No decorators, no policy registration, no middleware — just `Depends(require_role)`.

## Role Hierarchy

The library defines three standard roles with a hierarchical relationship:

| Role | Constant | Can Access |
|------|----------|------------|
| Admin | `RbacRoles.ADMIN` | Admin, Supervisor, Coordinator |
| Supervisor | `RbacRoles.SUPERVISOR` | Supervisor, Coordinator |
| Coordinator | `RbacRoles.COORDINATOR` | Coordinator only |

### Access Rules

- **Admin** can access any endpoint protected by any role
- **Supervisor** can access Supervisor and Coordinator endpoints (but not Admin)
- **Coordinator** can only access Coordinator endpoints

This is enforced via set intersection: if the user's roles overlap with the endpoint's allowed roles, access is granted.

## Integration Example

Complete FastAPI application with role-protected endpoints:

```python
from fastapi import FastAPI, Depends, HTTPException
from innov_lib_rbac import (
    get_current_user,
    require_admin,
    require_supervisor,
    require_coordinator,
    RbacRoles,
    InsufficientRoleException
)

app = FastAPI()

# 1. Define your authentication function
async def my_get_current_user():
    """
    Replace this with your actual authentication logic:
    - Decode JWT from Authorization header
    - Validate token with Entra ID
    - Extract roles from token claims
    - Return user dict with "roles" list
    """
    # Example: decode JWT and extract roles
    token = extract_bearer_token()  # Your function
    claims = validate_token(token)  # Your function
    
    return {
        "email": claims.get("preferred_username"),
        "name": claims.get("name"),
        "roles": claims.get("roles", [])  # List of role strings from Entra
    }

# 2. Override the library's placeholder
app.dependency_overrides[get_current_user] = my_get_current_user

# 3. Protect routes with role dependencies
@app.get("/api/dashboard")
async def get_dashboard(user=Depends(require_coordinator)):
    """Accessible by any authenticated user with Coordinator+ role"""
    return {"kpis": {...}}

@app.get("/api/queue/all")
async def get_all_queues(user=Depends(require_supervisor)):
    """Accessible by Supervisor or Admin only"""
    return {"queues": [...]}

@app.post("/api/admin/users")
async def manage_users(user=Depends(require_admin)):
    """Accessible by Admin only"""
    return {"users": [...]}

# 4. Optional: Add exception handler for cleaner error responses
@app.exception_handler(InsufficientRoleException)
async def insufficient_role_handler(request, exc: InsufficientRoleException):
    return exc.to_response()  # Returns 403 with {"detail": "Insufficient role"}
```

## User Model Requirements

The library expects users to have a `roles` field that is a **list of role strings**. Your `get_current_user` function must return a dict (or object) matching this structure:

```python
{
    "email": "user@dcli.com",
    "name": "John Doe",
    "roles": ["Coordinator", "Supervisor"]  # List of role strings
}
```

Role strings should match the constants defined in `RbacRoles`:
- `"Admin"`
- `"Supervisor"`
- `"Coordinator"`

The library uses set intersection to check access, so a user can have multiple roles (e.g., both Supervisor and Coordinator).

## API Reference

### Dependencies

| Function | Required Role | Admits |
|----------|---------------|--------|
| `require_coordinator` | Coordinator | Coordinator, Supervisor, Admin |
| `require_supervisor` | Supervisor | Supervisor, Admin |
| `require_admin` | Admin | Admin only |

All dependencies return the authenticated user dict/object.

### Role Constants

```python
from innov_lib_rbac import RbacRoles

RbacRoles.ADMIN        # "Admin"
RbacRoles.SUPERVISOR   # "Supervisor"
RbacRoles.COORDINATOR  # "Coordinator"
```

### Functions

#### `check_role(user, required_role: str) -> bool`

Programmatically check if a user has access to a specific role level.

```python
from innov_lib_rbac import check_role, RbacRoles

if check_role(user, RbacRoles.ADMIN):
    # User is Admin
    ...
elif check_role(user, RbacRoles.SUPERVISOR):
    # User is Supervisor or Admin
    ...
```

Returns `True` if the user's roles satisfy the required role level, `False` otherwise.

### Exceptions

#### `InsufficientRoleException`

Raised when a user lacks the required role for an endpoint.

- **Status Code:** 403 Forbidden
- **Response Body:** `{"detail": "Insufficient role: required X, user has [Y, Z]"}`

Add an exception handler to customize the response:

```python
@app.exception_handler(InsufficientRoleException)
async def handle_insufficient_role(request, exc):
    return JSONResponse(
        status_code=403,
        content={"error": "Access denied", "required": exc.required_role}
    )
```

## Azure AD/Entra ID Integration

The library expects roles to be present in the JWT token's `roles` claim. This claim should be configured in your Azure AD/Entra ID App Registration.

### Expected Token Structure

```json
{
  "preferred_username": "user@dcli.com",
  "name": "John Doe",
  "roles": ["Coordinator", "Supervisor"]
}
```

Your `get_current_user` function should decode this token and extract the `roles` claim into a list.

### Example with python-jose

```python
from jose import jwt, JWTError
from fastapi import HTTPException, Header

async def get_current_user_from_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(
            token,
            key=PUBLIC_KEY,  # Your Entra public key
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        )
        return {
            "email": payload.get("preferred_username"),
            "name": payload.get("name"),
            "roles": payload.get("roles", [])
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=innov_lib_rbac --cov-report=html
```

The library includes 26 tests covering:
- Role constant definitions
- Role hierarchy logic (Admin → all, Supervisor → Supervisor+Coordinator, Coordinator → Coordinator)
- All three dependencies (allow/deny cases)
- Exception behavior
- Edge cases (no roles, multiple roles, missing roles key)

## Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System design, role hierarchy logic, dependency injection pattern
- **[IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** — Step-by-step integration guide with real-world scenarios
- **[EXAMPLES.md](docs/EXAMPLES.md)** — Working code examples (basic, multi-role, service layer)

## Advanced Usage

### Programmatic Role Checks in Service Layer

```python
from innov_lib_rbac import check_role, RbacRoles

class TaskService:
    def get_tasks(self, user: dict):
        if check_role(user, RbacRoles.ADMIN):
            return self.repo.get_all_tasks()
        elif check_role(user, RbacRoles.SUPERVISOR):
            return self.repo.get_team_tasks(user["email"])
        elif check_role(user, RbacRoles.COORDINATOR):
            return self.repo.get_user_tasks(user["email"])
        else:
            raise InsufficientRoleException(RbacRoles.COORDINATOR, user.get("roles", []))
```

### Custom Role Hierarchies

If you need a different role structure, extend the `RbacRoles` class:

```python
from innov_lib_rbac import RbacRoles

class CustomRoles(RbacRoles):
    VIEWER = "Viewer"
    
    @classmethod
    def check_role(cls, user, required_role: str) -> bool:
        user_roles = set(user.get("roles", []))
        
        if required_role == cls.VIEWER:
            # Viewer requires explicit Viewer, Coordinator, Supervisor, or Admin role
            return bool(user_roles & {cls.VIEWER, cls.COORDINATOR, cls.SUPERVISOR, cls.ADMIN})
        
        # Fallback to default hierarchy
        return super().check_role(user, required_role)
```

## License

Internal DCLI library. Not for external distribution.

## Support

Contact: DCLI Innovation Team
