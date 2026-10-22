# Innov.Lib.Rbac FastAPI Example

Minimal FastAPI application demonstrating `innov-lib-rbac` role-based access control.

## What This Example Shows

- **JWT authentication setup** (mocked for demo — replace with real JWT validation in production)
- **Three-tier role hierarchy** (Admin > Supervisor > Coordinator)
- **Public endpoint** (`/public`) — no authentication required
- **Protected endpoints** with different role requirements:
  - `/me` — requires Coordinator or higher
  - `/supervisor` — requires Supervisor or Admin
  - `/admin` — requires Admin only
- **Role hierarchy in action** — Admin users can access Supervisor endpoints (inheritance)

## Quick Start

### 1. Install Dependencies

From this directory:

```bash
pip install -r requirements.txt
```

Or install the library from the parent directory in development mode:

```bash
pip install -e ..
```

### 2. Run the Application

```bash
uvicorn fastapi_app:app --reload
```

The app will start at `http://localhost:8000`

### 3. Test the Endpoints

Visit the interactive API docs at: `http://localhost:8000/docs`

Or use curl:

#### Public endpoint (no auth required):

```bash
curl http://localhost:8000/public
```

#### Get current user info (requires Coordinator+):

```bash
curl -H "Authorization: Bearer coordinator_token" http://localhost:8000/me
```

#### Supervisor endpoint (requires Supervisor or Admin):

```bash
# ✅ Works with supervisor_token
curl -H "Authorization: Bearer supervisor_token" http://localhost:8000/supervisor

# ✅ Works with admin_token (Admin inherits Supervisor privileges)
curl -H "Authorization: Bearer admin_token" http://localhost:8000/supervisor

# ❌ Fails with coordinator_token (insufficient role)
curl -H "Authorization: Bearer coordinator_token" http://localhost:8000/supervisor
```

#### Admin endpoint (requires Admin only):

```bash
# ✅ Works with admin_token
curl -H "Authorization: Bearer admin_token" http://localhost:8000/admin

# ❌ Fails with supervisor_token (insufficient role)
curl -H "Authorization: Bearer supervisor_token" http://localhost:8000/admin

# ❌ Fails with coordinator_token (insufficient role)
curl -H "Authorization: Bearer coordinator_token" http://localhost:8000/admin
```

## Mock Tokens

This example uses hardcoded tokens for demonstration. In production, use real JWT validation.

| Token | User | Roles |
|-------|------|-------|
| `coordinator_token` | coordinator@example.com | Coordinator |
| `supervisor_token` | supervisor@example.com | Supervisor, Coordinator |
| `admin_token` | admin@example.com | Admin, Supervisor, Coordinator |

## Role Hierarchy Demonstration

The example demonstrates how role hierarchy works:

1. **Coordinator** can access:
   - `/public` (no auth required)
   - `/me` (requires Coordinator+)

2. **Supervisor** can access:
   - Everything Coordinator can access, PLUS
   - `/supervisor` (requires Supervisor+)

3. **Admin** can access:
   - Everything Supervisor can access, PLUS
   - `/admin` (requires Admin only)

This hierarchy is automatic — you don't need to explicitly check for multiple roles. When you use `require_supervisor`, Admin users are automatically admitted.

## Code Structure

```python
from innov_lib_rbac import require_admin, require_supervisor, require_coordinator
from innov_lib_rbac.dependencies import get_current_user

# 1. Implement your authentication
def mock_get_current_user(authorization: str = Header(None)):
    # Validate JWT, extract user info
    return {
        "email": "user@example.com",
        "name": "User Name",
        "roles": ["Admin", "Supervisor", "Coordinator"]
    }

# 2. Override the library's placeholder
app.dependency_overrides[get_current_user] = mock_get_current_user

# 3. Protect endpoints with role dependencies
@app.get("/admin")
async def admin_endpoint(user: dict = Depends(require_admin)):
    return {"message": "Admin access granted"}
```

## Production Deployment

**⚠️ This example uses mock authentication for demonstration purposes.**

For production use:

1. Replace `mock_get_current_user` with real JWT validation
2. Use `python-jose` or equivalent to validate tokens against your identity provider
3. See `docs/IMPLEMENTATION_GUIDE.md` for complete production patterns with Azure AD / Entra ID

Example production pattern:

```python
from jose import jwt, JWTError
from fastapi import HTTPException, Header

JWKS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"

def get_current_user(authorization: str = Header(None)):
    token = extract_bearer_token(authorization)
    
    try:
        # Validate JWT signature against JWKS
        payload = jwt.decode(
            token,
            get_signing_key(token),
            algorithms=["RS256"],
            audience="your-client-id"
        )
        
        return {
            "email": payload.get("preferred_username"),
            "name": payload.get("name"),
            "roles": payload.get("roles", [])
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

See the full implementation guide for complete code.

## Further Reading

- **Complete implementation guide**: `../docs/IMPLEMENTATION_GUIDE.md`
- **Library API reference**: `../README.md`
- **Role hierarchy details**: `../innov_lib_rbac/roles.py`

## Troubleshooting

### 401 Unauthorized

- Missing `Authorization` header
- Invalid token format (must be `Bearer <token>`)
- Invalid token value

### 403 Forbidden

- Valid authentication but insufficient role
- Check the required role for the endpoint vs. your user's roles

### 501 Not Implemented

- `get_current_user` dependency not overridden
- Ensure `app.dependency_overrides[get_current_user] = your_implementation`

---

**Next Steps:**

1. Study this example to understand the pattern
2. Read `docs/IMPLEMENTATION_GUIDE.md` for production deployment
3. Integrate into your FastAPI application
4. Replace mock auth with real JWT validation
5. Configure Entra ID roles per the implementation guide
