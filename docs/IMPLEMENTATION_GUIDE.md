# Implementation Guide

Step-by-step guide for integrating `Innov.Lib.Rbac` into your FastAPI application.

---

## Prerequisites

- Python 3.8+
- FastAPI application
- Azure AD (Entra ID) authentication configured
- JWT tokens with roles claim

---

## Step 1: Install the Package

```bash
pip install git+https://github.com/org/Innov.Lib.Rbac.git
```

Or add to `requirements.txt`:

```
git+https://github.com/org/Innov.Lib.Rbac.git
```

---

## Step 2: Configure Entra ID Roles

### Create App Roles in Azure AD

1. Navigate to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Select your application
3. Go to **App roles** → **Create app role**

Create three roles:

| Display Name | Value | Description | Allowed member types |
|--------------|-------|-------------|---------------------|
| Admin | Admin | Full system access | Users/Groups |
| Supervisor | Supervisor | Supervisor-level access | Users/Groups |
| Coordinator | Coordinator | Coordinator-level access | Users/Groups |

### Assign Roles to Users

1. Go to **Enterprise Applications** → select your app
2. **Users and groups** → **Add user/group**
3. Select user and assign appropriate role

### Configure JWT Token Claims

Ensure your JWT tokens include the `roles` claim:

```json
{
  "aud": "api://your-client-id",
  "iss": "https://sts.windows.net/tenant-id/",
  "sub": "user-object-id",
  "roles": ["Admin", "Supervisor"],
  "email": "user@example.com",
  "name": "John Doe"
}
```

If the roles claim is missing, configure it in your app registration's **Token configuration** section.

---

## Step 3: Create `get_current_user` Dependency

This dependency extracts and validates the JWT token, returning a user dictionary with a `roles` key.

### Example Implementation

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Dict, List

# JWT configuration
AZURE_AD_TENANT_ID = "your-tenant-id"
AZURE_AD_CLIENT_ID = "your-client-id"
JWKS_URI = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/discovery/v2.0/keys"

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Extracts JWT token, validates it, and returns user info with roles.
    
    Returns:
        Dict with keys: 'email', 'name', 'roles' (list of role strings)
    """
    token = credentials.credentials
    
    try:
        # Decode and validate JWT (use python-jose or PyJWT)
        payload = jwt.decode(
            token,
            # In production, fetch and cache JWKS keys
            options={"verify_signature": False}  # For demo only
        )
        
        # Extract user info
        user = {
            "email": payload.get("email") or payload.get("preferred_username"),
            "name": payload.get("name"),
            "roles": payload.get("roles", [])  # CRITICAL: must return list
        }
        
        if not user["roles"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No roles found in token"
            )
        
        return user
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
```

### Production-Ready Version with JWKS Validation

```python
import requests
from jose import jwt, JWTError
from jose.backends import RSAKey
from functools import lru_cache

@lru_cache(maxsize=1)
def get_jwks():
    """Fetch and cache JWKS keys from Azure AD."""
    response = requests.get(JWKS_URI)
    return response.json()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    token = credentials.credentials
    
    try:
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]
        
        # Find matching key in JWKS
        jwks = get_jwks()
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find signing key"
            )
        
        # Validate and decode
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AZURE_AD_CLIENT_ID,
            issuer=f"https://sts.windows.net/{AZURE_AD_TENANT_ID}/"
        )
        
        return {
            "email": payload.get("email") or payload.get("preferred_username"),
            "name": payload.get("name"),
            "roles": payload.get("roles", [])
        }
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )
```

---

## Step 4: Protect Endpoints with Role Dependencies

Import the dependencies and apply them to your routes.

### Basic Usage

```python
from fastapi import FastAPI, Depends
from innov.lib.rbac import require_admin, require_supervisor, require_coordinator
from your_auth import get_current_user  # Your Step 3 implementation

app = FastAPI()

# Admin-only endpoint
@app.get("/api/admin/users")
def list_users(user: dict = Depends(require_admin(get_current_user))):
    return {"message": "Admin access granted", "user": user["name"]}

# Supervisor and above (includes Admin)
@app.get("/api/reports")
def view_reports(user: dict = Depends(require_supervisor(get_current_user))):
    return {"message": "Supervisor access granted", "user": user["name"]}

# Coordinator and above (includes Supervisor and Admin)
@app.post("/api/tasks")
def create_task(user: dict = Depends(require_coordinator(get_current_user))):
    return {"message": "Task created", "user": user["name"]}
```

### Role Hierarchy

The library enforces a three-tier hierarchy with automatic inheritance:

```
Admin
  └─ Supervisor
       └─ Coordinator
```

- `require_admin` → Admin only
- `require_supervisor` → Supervisor + Admin
- `require_coordinator` → Coordinator + Supervisor + Admin

### Multiple Dependencies

Combine with other dependencies:

```python
from fastapi import Depends, Query
from your_app.database import get_db
from sqlalchemy.orm import Session

@app.get("/api/tasks")
def list_tasks(
    user: dict = Depends(require_coordinator(get_current_user)),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100)
):
    tasks = db.query(Task).filter_by(user_id=user["email"]).limit(limit).all()
    return {"tasks": tasks}
```

### Router-Level Protection

Apply to entire routers:

```python
from fastapi import APIRouter, Depends

admin_router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(require_admin(get_current_user))]
)

@admin_router.get("/users")
def list_users():
    # All routes in this router require Admin
    return {"users": [...]}

@admin_router.delete("/users/{user_id}")
def delete_user(user_id: str):
    return {"deleted": user_id}

app.include_router(admin_router)
```

---

## Step 5: Test Role Enforcement

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient
from your_app.main import app

client = TestClient(app)

def test_admin_endpoint_requires_admin():
    # No token
    response = client.get("/api/admin/users")
    assert response.status_code == 403
    
    # Coordinator token (insufficient)
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 403
    
    # Admin token (success)
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 200

def test_hierarchy_enforcement():
    # Admin can access Supervisor endpoints
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/reports", headers=headers)
    assert response.status_code == 200
    
    # Supervisor can access Coordinator endpoints
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    response = client.post("/api/tasks", headers=headers)
    assert response.status_code == 200
```

### Manual Testing with curl

```bash
# Get a token from Azure AD
TOKEN="your-jwt-token"

# Test Coordinator endpoint (should work for all roles)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/tasks

# Test Supervisor endpoint (should work for Supervisor and Admin)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/reports

# Test Admin endpoint (should work for Admin only)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/users
```

### Testing Locally with Mock Tokens

For local development, create a mock dependency:

```python
from typing import Dict

def mock_get_current_user(role: str = "Admin") -> Dict:
    """Mock user for local testing."""
    return {
        "email": "test@example.com",
        "name": "Test User",
        "roles": [role]
    }

# In development, override the real dependency
if app.debug:
    app.dependency_overrides[get_current_user] = lambda: mock_get_current_user("Admin")
```

---

## Migration from Inline Role Checks

### Before: Inline Role Logic

```python
from fastapi import HTTPException, status

@app.get("/api/admin/users")
def list_users(current_user: dict = Depends(get_current_user)):
    # Inline role check (repeated across endpoints)
    user_roles = set(current_user.get("roles", []))
    admin_roles = {"Admin"}
    
    if not user_roles.intersection(admin_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    # Business logic
    return {"users": [...]}

@app.get("/api/reports")
def view_reports(current_user: dict = Depends(get_current_user)):
    # Duplicate role check with different roles
    user_roles = set(current_user.get("roles", []))
    allowed_roles = {"Admin", "Supervisor"}
    
    if not user_roles.intersection(allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor role required"
        )
    
    return {"reports": [...]}
```

**Problems:**
- Duplicated role-checking logic across every endpoint
- Easy to make mistakes (typos in role names, inconsistent error messages)
- Hard to test (business logic mixed with authorization)
- No clear hierarchy enforcement

### After: Using `Innov.Lib.Rbac`

```python
from innov.lib.rbac import require_admin, require_supervisor

@app.get("/api/admin/users")
def list_users(user: dict = Depends(require_admin(get_current_user))):
    # Role check handled by dependency
    return {"users": [...]}

@app.get("/api/reports")
def view_reports(user: dict = Depends(require_supervisor(get_current_user))):
    # Hierarchy automatically enforced (Admin + Supervisor allowed)
    return {"reports": [...]}
```

**Benefits:**
- No inline role checks — authorization separated from business logic
- Consistent error handling (403 with standard message)
- Testable (override `get_current_user` in tests)
- Clear hierarchy (Admin automatically has Supervisor access)
- Self-documenting (endpoint signature shows required role)

### Migration Checklist

1. **Identify all inline role checks** — search codebase for `current_user.get("roles")` or similar
2. **Replace with appropriate dependency** — `require_admin`, `require_supervisor`, or `require_coordinator`
3. **Remove inline `HTTPException` raises** — dependency handles this
4. **Update tests** — mock `get_current_user` instead of mocking role checks
5. **Verify hierarchy behavior** — ensure Admins can still access Supervisor/Coordinator endpoints

---

## Troubleshooting

### 403 Forbidden: Insufficient Role

**Symptom:** `{"detail": "Insufficient role: required Admin, Supervisor; user has Coordinator"}`

**Causes:**
1. User does not have the required role assigned in Azure AD
2. JWT token does not include the `roles` claim
3. Role names in Azure AD do not match expected values (`Admin`, `Supervisor`, `Coordinator`)

**Solutions:**
- Verify user has correct role in **Azure Portal** → **Enterprise Applications** → your app → **Users and groups**
- Check JWT token payload (decode at [jwt.io](https://jwt.io)) — ensure `roles` claim is present and correct
- Ensure role names in Azure AD exactly match `Admin`, `Supervisor`, `Coordinator` (case-sensitive)

### 403 Forbidden: No Roles Found

**Symptom:** `{"detail": "No roles found in token"}`

**Cause:** JWT token missing `roles` claim entirely.

**Solutions:**
1. Configure **Token configuration** in Azure AD app registration:
   - Add `roles` as an optional claim
   - Enable "Include roles in the token"
2. Ensure user has at least one role assigned
3. Force a fresh token (logout and login again)

### 401 Unauthorized: Token Validation Failed

**Symptom:** `{"detail": "Token validation failed: Signature verification failed"}`

**Causes:**
- Token expired
- Token signed by wrong issuer
- JWKS keys not fetched correctly
- Audience/issuer mismatch

**Solutions:**
- Check token expiration (`exp` claim)
- Verify `AZURE_AD_TENANT_ID` and `AZURE_AD_CLIENT_ID` match your app registration
- Ensure JWKS URI is correct: `https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys`
- Test with `options={"verify_signature": False}` temporarily to isolate issue (never use in production)

### Role Hierarchy Not Working

**Symptom:** Admin users getting 403 on Supervisor endpoints.

**Cause:** Custom `RbacRoles` subclass with incorrect hierarchy configuration.

**Solution:**
Verify hierarchy in your custom class:

```python
class CustomRbac(RbacRoles):
    ALLOWED_ROLES = {
        "Admin": {"Admin", "Supervisor", "Coordinator"},  # Must include lower roles
        "Supervisor": {"Supervisor", "Coordinator"},
        "Coordinator": {"Coordinator"}
    }
```

If using default `RbacRoles`, this should work automatically.

### Dependency Injection Not Working

**Symptom:** `get_current_user` not called or returns `None`.

**Causes:**
- Forgot to pass `get_current_user` to `require_*` factory
- Middleware stripping `Authorization` header
- CORS issues preventing header from reaching backend

**Solutions:**
- Always call dependency factory: `require_admin(get_current_user)` (not just `require_admin`)
- Check FastAPI middleware order — auth should run before RBAC
- Test with curl/Postman to isolate frontend CORS issues

### InsufficientRoleException Not Caught

**Symptom:** Unhandled exception or 500 error instead of 403.

**Cause:** Custom exception handler interfering with FastAPI's default handling.

**Solution:**
Ensure FastAPI can handle `InsufficientRoleException` → HTTPException translation:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from innov.lib.rbac import InsufficientRoleException

@app.exception_handler(InsufficientRoleException)
async def rbac_exception_handler(request: Request, exc: InsufficientRoleException):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)}
    )
```

This should not be necessary (the dependency already raises `HTTPException`), but useful if you've customized exception handling.

---

## Next Steps

- Read [ARCHITECTURE.md](./ARCHITECTURE.md) for design details and extensibility
- See [examples/](../examples/) for complete working applications
- Review FastAPI's [dependency injection docs](https://fastapi.tiangolo.com/tutorial/dependencies/)
- Explore Azure AD [app roles documentation](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-add-app-roles-in-azure-ad-apps)

---

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Contact the Innovation team
- Review existing Azure AD + FastAPI integration patterns in other DCLI projects
