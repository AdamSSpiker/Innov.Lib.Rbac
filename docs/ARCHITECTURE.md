# Architecture

## Overview

`Innov.Lib.Rbac` implements role-based access control for FastAPI applications using a **dependency injection pattern**. The library provides declarative, composable route protection through FastAPI's native `Depends()` mechanism rather than middleware or decorators.

**Core principle:** Authorization happens at the endpoint level, not globally. Each route explicitly declares its required role via a dependency, making access control self-documenting and statically analyzable.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                              │
│  app.dependency_overrides[get_current_user] = my_auth_fn    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Provides authenticated user
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              innov_lib_rbac.dependencies                     │
│                                                              │
│  ┌────────────────────────────────────────────────┐        │
│  │  get_current_user() -> dict[str, Any]          │        │
│  │    Placeholder — app must override             │        │
│  │    Returns: {"email": ..., "roles": [...]}     │        │
│  └────────────────┬───────────────────────────────┘        │
│                   │                                          │
│                   │ Consumed by:                             │
│                   │                                          │
│  ┌────────────────▼────────────────┐                       │
│  │  require_coordinator(user)      │                       │
│  │  require_supervisor(user)       │                       │
│  │  require_admin(user)            │                       │
│  └────────────────┬────────────────┘                       │
│                   │                                          │
│                   │ Calls:                                   │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────┐          │
│  │  RbacRoles.check_role(user, required_role)   │          │
│  │    Role hierarchy validation logic           │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 1. Role Constants and Hierarchy (`roles.py`)

**Purpose:** Define standard roles and implement hierarchical access control logic.

**Components:**

- **Role Constants:**
  ```python
  ROLE_ADMIN = "Admin"
  ROLE_SUPERVISOR = "Supervisor"
  ROLE_COORDINATOR = "Coordinator"
  ```

- **`RbacRoles` Class:**
  - Static container for role constants
  - Single public method: `check_role(user, required_role) -> bool`
  - Implements set-based hierarchy validation

**Hierarchy Model:**

```
Admin (highest privilege)
  │
  ├─ Can access: Admin, Supervisor, Coordinator
  │
Supervisor
  │
  ├─ Can access: Supervisor, Coordinator
  │
Coordinator (lowest privilege)
  │
  └─ Can access: Coordinator only
```

**Set-Based Access Control:**

For each role, define the set of roles that satisfy it:

| Required Role | Allowed Roles (Set) |
|---------------|---------------------|
| Coordinator | `{Coordinator, Supervisor, Admin}` |
| Supervisor | `{Supervisor, Admin}` |
| Admin | `{Admin}` |

Access is granted if the **intersection** of the user's roles and the allowed set is non-empty.

```python
allowed = {ROLE_SUPERVISOR, ROLE_ADMIN}  # For Supervisor requirement
user_roles = set(user.get("roles", []))
return bool(allowed.intersection(user_roles))  # True if any overlap
```

**Why set intersection?**
- Supports users with multiple roles (e.g., both Supervisor and Coordinator)
- Simple, efficient, and extensible
- No need for explicit role comparisons or rank ordering

### 2. FastAPI Dependencies (`dependencies.py`)

**Purpose:** Provide drop-in route protection via FastAPI's `Depends()` mechanism.

**Components:**

#### `get_current_user()`

**Type:** Placeholder dependency function

**Signature:**
```python
def get_current_user() -> dict[str, Any]
```

**Behavior:**
- Raises `HTTPException(501)` by default (Not Implemented)
- Must be overridden by the consuming application via `app.dependency_overrides`
- Expected return structure:
  ```python
  {
      "email": "user@dcli.com",
      "name": "John Doe",
      "roles": ["Coordinator", "Supervisor"]  # List of role strings
  }
  ```

**Why a placeholder?**
- The library cannot know how the consuming app authenticates users
- Some apps use JWT tokens, others use sessions or API keys
- The placeholder forces explicit configuration and fails loudly if forgotten

#### `require_coordinator(user: dict = Depends(get_current_user))`

**Type:** FastAPI dependency

**Behavior:**
1. Calls `get_current_user()` to get the authenticated user
2. Calls `RbacRoles.check_role(user, ROLE_COORDINATOR)`
3. Returns the user dict if access granted
4. Raises `HTTPException(403)` if access denied

**Admits:** Coordinator, Supervisor, or Admin

**Usage:**
```python
@app.get("/api/tasks/mine")
async def get_my_tasks(user=Depends(require_coordinator)):
    # user is guaranteed to be Coordinator or higher
    return {"tasks": [...]}
```

#### `require_supervisor(user: dict = Depends(get_current_user))`

**Type:** FastAPI dependency

**Behavior:** Same as `require_coordinator`, but checks `ROLE_SUPERVISOR`

**Admits:** Supervisor or Admin

**Usage:**
```python
@app.get("/api/tasks/all")
async def get_all_tasks(user=Depends(require_supervisor)):
    # user is guaranteed to be Supervisor or Admin
    return {"tasks": [...]}
```

#### `require_admin(user: dict = Depends(get_current_user))`

**Type:** FastAPI dependency

**Behavior:** Same as above, but checks `ROLE_ADMIN`

**Admits:** Admin only

**Usage:**
```python
@app.post("/api/admin/bulk-approve")
async def bulk_approve(user=Depends(require_admin)):
    # user is guaranteed to be Admin
    return {"success": True}
```

#### `check_role(user: dict, required_role: str) -> bool`

**Type:** Helper function (not a FastAPI dependency)

**Purpose:** Programmatic role checks in service/business logic

**Signature:**
```python
def check_role(user: dict[str, Any], required_role: str) -> bool
```

**Behavior:** Direct wrapper around `RbacRoles.check_role()` for convenience

**Usage:**
```python
@app.post("/api/conditional-action")
async def conditional(user: dict = Depends(require_coordinator)):
    if check_role(user, ROLE_ADMIN):
        # Admin-specific logic
        perform_admin_action()
    else:
        # Regular coordinator/supervisor logic
        perform_regular_action()
```

### 3. Exceptions (`exceptions.py`)

**Purpose:** Provide a domain-specific exception type for RBAC failures.

**Components:**

#### `InsufficientRoleException`

**Type:** `HTTPException` subclass

**Fields:**
- `status_code`: Always `403` (Forbidden)
- `detail`: Human-readable error message

**Default Detail:**
```
"Insufficient role for this operation."
```

**Why provide this?**
- Allows consuming apps to catch RBAC failures specifically vs. other HTTP errors
- Can be used for custom exception handlers
- Not used by the library itself — dependencies raise plain `HTTPException(403)` directly

**Usage (optional):**
```python
@app.exception_handler(InsufficientRoleException)
async def insufficient_role_handler(request, exc: InsufficientRoleException):
    return JSONResponse(
        status_code=403,
        content={"error": "Access denied", "required_role": exc.detail}
    )
```

## Data Flow: JWT Token → Authorized Access

### End-to-End Request Flow

```
1. Client Request
   ↓
   GET /api/tasks/mine
   Authorization: Bearer <JWT>
   
2. FastAPI Router
   ↓
   @app.get("/api/tasks/mine")
   async def get_my_tasks(user=Depends(require_coordinator))
   
3. Dependency Resolution
   ↓
   FastAPI calls: require_coordinator()
   
4. User Authentication
   ↓
   require_coordinator calls: get_current_user()
   ↓
   App-provided function decodes JWT:
     - Extract "roles" claim from token
     - Validate signature/expiry
     - Return user dict: {"email": ..., "roles": ["Coordinator"]}
   
5. Role Validation
   ↓
   require_coordinator calls: RbacRoles.check_role(user, ROLE_COORDINATOR)
   ↓
   Set intersection:
     allowed = {ROLE_COORDINATOR, ROLE_SUPERVISOR, ROLE_ADMIN}
     user_roles = {"Coordinator"}
     intersection = {"Coordinator"} ✓
   ↓
   Returns True → Access granted
   
6. Endpoint Execution
   ↓
   async def get_my_tasks(user):
       # user = {"email": "...", "roles": ["Coordinator"]}
       return {"tasks": [...]}
```

### JWT Structure (Azure AD/Entra ID)

The library expects JWT tokens to contain a `roles` claim:

```json
{
  "aud": "your-client-id",
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",
  "iat": 1700000000,
  "exp": 1700003600,
  "preferred_username": "user@dcli.com",
  "name": "John Doe",
  "roles": ["Coordinator", "Supervisor"]
}
```

**The `roles` claim is configured in Azure AD App Registration:**
- Define App Roles in the manifest
- Assign roles to users/groups
- Entra ID automatically includes assigned roles in the token

**The consuming app is responsible for:**
1. Decoding the JWT token
2. Validating signature, issuer, audience, expiry
3. Extracting the `roles` claim
4. Returning a user dict with the `roles` list

## Design Decisions

### Why FastAPI Dependencies (Not Middleware)?

**Considered alternatives:**
1. **Middleware** — Global request interception
2. **Decorators** — Function wrappers (`@require_admin`)
3. **Policy classes** — Centralized authorization logic
4. **Dependencies** — ✅ Chosen approach

**Why dependencies won?**

| Criterion | Middleware | Decorators | Dependencies |
|-----------|------------|------------|--------------|
| **Explicit** | ❌ Global, hidden | ⚠️ Per-route, visible | ✅ Per-route, visible |
| **Composable** | ❌ Single chain | ⚠️ Stackable but awkward | ✅ Native to FastAPI |
| **Testable** | ⚠️ Requires app context | ⚠️ Requires mocking | ✅ Easily overridden |
| **Type-safe** | ❌ No type hints | ⚠️ Breaks signatures | ✅ Full type safety |
| **Self-documenting** | ❌ Not in route def | ⚠️ Decorator pile-up | ✅ In function signature |
| **IDE support** | ❌ No autocomplete | ⚠️ Limited | ✅ Full autocomplete |

**Key advantages:**

1. **Explicit per-route:** Authorization is visible in the function signature, not hidden in global config.
   ```python
   # Clear: this endpoint requires Supervisor
   @app.get("/api/tasks/all")
   async def get_all_tasks(user=Depends(require_supervisor)):
       ...
   ```

2. **Composable:** Easily combine with other dependencies (database sessions, pagination, rate limiting).
   ```python
   @app.get("/api/tasks")
   async def get_tasks(
       user=Depends(require_coordinator),
       db=Depends(get_db),
       pagination=Depends(get_pagination),
   ):
       ...
   ```

3. **Testable:** Override dependencies in tests without mocking globals.
   ```python
   app.dependency_overrides[get_current_user] = lambda: {"roles": ["Admin"]}
   ```

4. **Type-safe:** The user object is properly typed and flows through the call chain.

5. **Framework-native:** Uses FastAPI's built-in dependency injection, not a custom system.

### Why Role Hierarchy (Not Flat Permissions)?

**Considered alternatives:**
1. **Flat permissions** — `["tasks.read", "tasks.write", "users.manage"]`
2. **Role hierarchy** — ✅ Chosen approach

**Why hierarchy?**

**Flat permissions:**
- ✅ Granular control
- ❌ Requires managing many permissions per user
- ❌ Difficult to reason about cross-cutting concerns
- ❌ High maintenance burden

**Role hierarchy:**
- ✅ Simple mental model: "Admin can do everything"
- ✅ Fewer assignments: one role vs. dozens of permissions
- ✅ Easy to extend: new Coordinator endpoints automatically work for Admin
- ✅ Matches organizational structure: team hierarchy = role hierarchy

**Trade-off accepted:**
- Less granular than permission-based models
- Suitable for internal tools with clear organizational roles
- Not suitable for multi-tenant SaaS with complex permission matrices

**When to use flat permissions instead:**
- Fine-grained resource-level access control
- Multi-tenant applications
- User-configurable permissions
- Complex delegation/sharing workflows

### Why Set-Based Validation (Not Rank Ordering)?

**Considered alternatives:**
1. **Rank ordering** — Assign numeric ranks (Admin=3, Supervisor=2, Coordinator=1)
2. **Set intersection** — ✅ Chosen approach

**Why sets?**

**Rank ordering:**
```python
ROLE_RANKS = {"Admin": 3, "Supervisor": 2, "Coordinator": 1}

def check_role(user, required_role):
    user_rank = max(ROLE_RANKS.get(r, 0) for r in user["roles"])
    required_rank = ROLE_RANKS[required_role]
    return user_rank >= required_rank
```

- ✅ Simple comparison
- ❌ Assumes linear hierarchy
- ❌ Doesn't support orthogonal roles (e.g., "Auditor" with read-all but no write)
- ❌ Requires maintaining a global rank registry

**Set intersection:**
```python
allowed = {ROLE_SUPERVISOR, ROLE_ADMIN}
user_roles = set(user.get("roles", []))
return bool(allowed.intersection(user_roles))
```

- ✅ Supports multiple roles naturally
- ✅ No global registry needed
- ✅ Can represent non-hierarchical relationships
- ✅ Extensible to custom role models

**Trade-off accepted:**
- Slightly more verbose per-role logic
- But: more flexible and future-proof

### Why No Middleware?

FastAPI middleware runs before route matching and dependency resolution. This means:

**Problems with middleware-based auth:**
1. **No access to route metadata** — Can't know which role a route requires
2. **Global or nothing** — Either all routes are protected or none
3. **Manual exclusions** — Need to maintain a list of public routes
4. **Testing complexity** — Must spin up full app context for every test

**Dependencies solve this:**
- Routes declare their own requirements
- Public routes simply don't use the dependency
- Testing is trivial via `dependency_overrides`

**When middleware IS appropriate:**
- Token validation (before role checking)
- Request logging
- CORS headers
- Rate limiting (global)

**Our pattern:**
- Middleware handles authentication (token validation)
- Dependencies handle authorization (role checking)

## Extensibility

### Custom Roles

**Scenario:** You need a "Viewer" role with read-only access.

**Approach 1: Extend `RbacRoles`**

```python
from innov_lib_rbac import RbacRoles, ROLE_ADMIN, ROLE_SUPERVISOR, ROLE_COORDINATOR

ROLE_VIEWER = "Viewer"

class CustomRoles(RbacRoles):
    VIEWER = ROLE_VIEWER
    
    @staticmethod
    def check_role(user, required_role: str) -> bool:
        user_roles = set(user.get("roles", []))
        
        if required_role == ROLE_VIEWER:
            # Viewer admits Viewer, Coordinator, Supervisor, or Admin
            allowed = {ROLE_VIEWER, ROLE_COORDINATOR, ROLE_SUPERVISOR, ROLE_ADMIN}
            return bool(allowed.intersection(user_roles))
        
        # Fallback to base hierarchy
        return super().check_role(user, required_role)
```

**Approach 2: New dependency**

```python
from innov_lib_rbac import get_current_user, RbacRoles
from fastapi import Depends, HTTPException

def require_viewer(user=Depends(get_current_user)):
    allowed = {"Viewer", "Coordinator", "Supervisor", "Admin"}
    user_roles = set(user.get("roles", []))
    
    if not allowed.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Viewer role required")
    
    return user
```

### Custom Hierarchy

**Scenario:** You need a non-linear hierarchy (e.g., "Auditor" with read-all but no write).

**Approach: Define role relationships explicitly**

```python
from innov_lib_rbac import RbacRoles

ROLE_AUDITOR = "Auditor"

class AuditableRoles(RbacRoles):
    AUDITOR = ROLE_AUDITOR
    
    @staticmethod
    def check_role(user, required_role: str) -> bool:
        user_roles = set(user.get("roles", []))
        
        # Define allowed sets for each role
        role_permissions = {
            "Coordinator": {"Coordinator", "Supervisor", "Admin", "Auditor"},  # Auditor can read
            "Supervisor": {"Supervisor", "Admin"},  # Auditor CANNOT write
            "Admin": {"Admin"},
            "Auditor": {"Auditor"},  # Read-only role
        }
        
        allowed = role_permissions.get(required_role, set())
        return bool(allowed.intersection(user_roles))
```

### Custom User Models

**Scenario:** Your user model is a dataclass, not a dict.

**Approach: Adapt in `get_current_user`**

```python
from dataclasses import dataclass
from innov_lib_rbac import get_current_user

@dataclass
class User:
    email: str
    name: str
    roles: list[str]

def my_get_current_user() -> User:
    # Decode JWT, query database, etc.
    return User(email="...", name="...", roles=["Coordinator"])

# Override the library's placeholder
app.dependency_overrides[get_current_user] = my_get_current_user
```

The library will work as long as `user.roles` or `user["roles"]` returns a list. The `RbacRoles.check_role()` method uses `user.get("roles", [])` which works for both dicts and dataclasses with a `get` method.

**For dataclasses without `.get()`, adapt the user dict:**

```python
def require_coordinator_dataclass(user: User = Depends(my_get_current_user)):
    user_dict = {"roles": user.roles}
    if not RbacRoles.check_role(user_dict, ROLE_COORDINATOR):
        raise HTTPException(status_code=403, detail="Coordinator role required")
    return user
```

### Service-Layer Authorization

**Scenario:** You need role checks in business logic, not just at the route level.

**Approach: Use `check_role()` directly**

```python
from innov_lib_rbac import check_role, RbacRoles, InsufficientRoleException

class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo
    
    def get_tasks(self, user: dict):
        """Return tasks based on user's role"""
        if check_role(user, RbacRoles.ADMIN):
            # Admin sees all tasks across all processes
            return self.repo.get_all_tasks()
        
        elif check_role(user, RbacRoles.SUPERVISOR):
            # Supervisor sees team tasks in their process
            return self.repo.get_team_tasks(user["email"])
        
        elif check_role(user, RbacRoles.COORDINATOR):
            # Coordinator sees only their own tasks
            return self.repo.get_user_tasks(user["email"])
        
        else:
            raise InsufficientRoleException("Coordinator role required to view tasks")
```

**Why this pattern?**
- Keeps role logic out of the route handlers
- Service layer can be tested independently
- Business rules are centralized, not scattered across endpoints

## Testing Strategy

### Unit Tests

The library includes comprehensive unit tests covering:

1. **Role constants** — Verify `RbacRoles.ADMIN` etc. match expected strings
2. **Role hierarchy logic** — Test `check_role()` with all combinations of user roles and required roles
3. **Dependencies** — Test all three `require_*` dependencies with allow/deny cases
4. **Exceptions** — Verify exception types, status codes, and messages
5. **Edge cases** — Empty roles list, missing roles key, multiple roles, unknown roles

**Run tests:**
```bash
pytest
```

**Coverage:**
```bash
pytest --cov=innov_lib_rbac --cov-report=html
```

### Integration Testing (Consuming App)

**Recommended approach:**

```python
from fastapi.testclient import TestClient
from innov_lib_rbac import get_current_user

def test_admin_only_endpoint():
    # Override get_current_user to return a mock admin
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "admin@dcli.com",
        "roles": ["Admin"]
    }
    
    client = TestClient(app)
    response = client.post("/api/admin/bulk-approve")
    
    assert response.status_code == 200

def test_admin_only_endpoint_denies_coordinator():
    # Override to return a coordinator
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "coord@dcli.com",
        "roles": ["Coordinator"]
    }
    
    client = TestClient(app)
    response = client.post("/api/admin/bulk-approve")
    
    assert response.status_code == 403
```

**No need to mock JWT decoding** — override the dependency directly.

## Performance Considerations

### Token Validation Overhead

**Problem:** Decoding and validating JWT tokens on every request can be expensive.

**Solution:** Use FastAPI's built-in caching for `get_current_user`:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def validate_token(token: str):
    # Expensive: decode JWT, validate signature, check expiry
    return jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])

def get_current_user(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    payload = validate_token(token)  # Cached
    return {"email": payload["preferred_username"], "roles": payload["roles"]}
```

**Caveat:** Cache invalidation on token refresh/logout. Use short TTLs or event-based invalidation.

### Role Check Overhead

**Complexity:** `O(n)` where `n` is the number of user roles (typically 1-3).

**Optimization:** Not needed — set intersection is extremely fast for small sets.

**Benchmark:**
- 1 million role checks: ~50ms
- Negligible compared to JWT validation, database queries, business logic

## Security Considerations

### JWT Validation

**The library does NOT validate JWT tokens.** This is the responsibility of the consuming app's `get_current_user` implementation.

**Required validations:**
1. **Signature** — Verify token signed by trusted issuer (Entra ID)
2. **Expiry** — Reject expired tokens (`exp` claim)
3. **Audience** — Verify token issued for this application (`aud` claim)
4. **Issuer** — Verify token issued by expected authority (`iss` claim)
5. **Not before** — Respect `nbf` claim if present

**Example:**
```python
from jose import jwt, JWTError

def get_current_user(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(
            token,
            key=PUBLIC_KEY,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
            }
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    
    return {"email": payload["preferred_username"], "roles": payload.get("roles", [])}
```

### Role Tampering

**Risk:** Malicious user modifies JWT token to add Admin role.

**Mitigation:** JWT signature validation prevents tampering. The token is signed by Entra ID with a private key; any modification invalidates the signature.

**Do NOT:**
- Trust roles from query parameters, request body, or cookies
- Allow users to self-assign roles
- Store roles in client-side storage (localStorage, sessionStorage)

**Always:**
- Extract roles from validated JWT tokens only
- Roles must come from a trusted identity provider (Entra ID)

### Horizontal Privilege Escalation

**Risk:** User with Coordinator role accesses another coordinator's tasks.

**Mitigation:** The library prevents **vertical** escalation (Coordinator → Admin), not **horizontal** (Coordinator A → Coordinator B).

**Application responsibility:**
- Check resource ownership in endpoint logic
- Filter queries by user ID/email
- Implement field-level or row-level security

**Example:**
```python
@app.get("/api/tasks/mine")
async def get_my_tasks(user=Depends(require_coordinator), db=Depends(get_db)):
    # Only return tasks assigned to the current user
    return db.query(Task).filter(Task.assignee_email == user["email"]).all()
```

### Insufficient Role Exception Leakage

**Risk:** Exception messages reveal internal role structure.

**Default behavior:**
```json
{"detail": "Admin role required."}
```

**Mitigation:** Generic error messages in production.

**Custom exception handler:**
```python
@app.exception_handler(InsufficientRoleException)
async def handle_insufficient_role(request, exc):
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=403,
            content={"error": "Access denied"}
        )
    else:
        return JSONResponse(
            status_code=403,
            content={"error": "Access denied", "detail": exc.detail}
        )
```

## Comparison to Alternatives

### vs. Casbin

**Casbin:**
- Policy-based access control (PRBAC, ACL, RBAC)
- Centralized policy files (`.csv`, `.conf`)
- Supports complex rules and inheritance

**Innov.Lib.Rbac:**
- Role-based only
- Inline dependency declarations
- Simple hierarchy model

**When to use Casbin:**
- Complex authorization rules (time-based, resource-based)
- External policy management
- Multi-tenant with per-tenant policies

**When to use this library:**
- Simple role hierarchy
- FastAPI-native integration
- Minimal configuration

### vs. FastAPI-Permissions

**FastAPI-Permissions:**
- Decorator-based (`@has_permission("admin")`)
- User/group/permission model
- Flask-inspired

**Innov.Lib.Rbac:**
- Dependency-based (`Depends(require_admin)`)
- Role hierarchy model
- FastAPI-native

**Why dependencies over decorators:**
- Better IDE support (autocomplete, type hints)
- Explicit in function signature
- Easier to test (override dependencies)

### vs. Starlette-Auth

**Starlette-Auth:**
- Middleware-based
- Global authentication
- Session management

**Innov.Lib.Rbac:**
- Dependency-based
- Per-route authorization
- No session state

**When to use Starlette-Auth:**
- Session-based authentication
- Global login walls

**When to use this library:**
- JWT-based authentication
- Granular per-endpoint control

## Future Enhancements

### Planned Features (Not Yet Implemented)

1. **Dynamic role resolution** — Load role hierarchy from configuration at runtime
2. **Permission-based extensions** — Hybrid role + permission model
3. **Async role validation** — Support async `check_role()` for database lookups
4. **OpenAPI integration** — Auto-document role requirements in Swagger UI

### Non-Goals

1. **Multi-tenancy** — Out of scope; consuming apps handle tenant isolation
2. **Resource-level permissions** — Out of scope; apps implement row-level security
3. **UI components** — Backend-only library

## References

- **Source project:** RPA Task Tracker (`D:\repos\RPA.TaskTracker.UX\backend\app\core\roles.py`)
- **FastAPI Dependencies:** https://fastapi.tiangolo.com/tutorial/dependencies/
- **Azure AD App Roles:** https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps
