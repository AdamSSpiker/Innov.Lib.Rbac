# Integration Guide

This document explains how to integrate Innov.Lib.Rbac into your ASP.NET Core application.

## Prerequisites

- .NET 8.0 or higher
- ASP.NET Core application with JWT authentication
- Azure AD/Entra app registration with role assignments

## Step-by-Step Integration

### 1. Install the Package

```bash
dotnet add package Innov.Lib.Rbac
```

### 2. Configure Azure AD/Entra Roles

In your Azure AD/Entra App Registration:

1. Navigate to **App roles** → **Create app role**
2. Create three roles:
   - Display name: `Admin`, Value: `Admin`, Allowed member types: `Users/Groups`
   - Display name: `Supervisor`, Value: `Supervisor`, Allowed member types: `Users/Groups`
   - Display name: `Coordinator`, Value: `Coordinator`, Allowed member types: `Users/Groups`
3. Assign users/groups to roles in **Enterprise Applications** → Your app → **Users and groups**

### 3. Update appsettings.json

```json
{
  "AzureAd": {
    "TenantId": "your-tenant-guid",
    "ClientId": "your-client-guid",
    "Instance": "https://login.microsoftonline.com/"
  }
}
```

### 4. Update Program.cs

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// Configure Azure AD JWT authentication
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        var azureAd = builder.Configuration.GetSection("AzureAd");
        options.Authority = $"{azureAd["Instance"]}{azureAd["TenantId"]}/v2.0";
        options.Audience = azureAd["ClientId"];
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ClockSkew = TimeSpan.FromMinutes(5)
        };
    });

// Add RBAC policies
builder.Services.AddRbacPolicies();

builder.Services.AddControllers();

var app = builder.Build();

// CRITICAL: Order matters
app.UseAuthentication();      // 1. Validate JWT token
app.UseRbacMiddleware();       // 2. Enrich role claims
app.UseAuthorization();        // 3. Check policies

app.MapControllers();
app.Run();
```

### 5. Apply to Controllers

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/[controller]")]
public class MyController : ControllerBase
{
    // Any authenticated user with Coordinator+ role
    [HttpGet]
    [RequireRole(RbacRoles.Coordinator, RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult Get()
    {
        return Ok();
    }

    // Supervisor or Admin only
    [HttpGet("admin")]
    [RequireRole(RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult GetAdminData()
    {
        return Ok();
    }

    // Admin only
    [HttpPost("configure")]
    [RequireRole(RbacRoles.Admin)]
    public IActionResult Configure()
    {
        return Ok();
    }
}
```

### 6. Use in Minimal APIs

```csharp
using Innov.Lib.Rbac;

app.MapGet("/api/data", () => Results.Ok())
    .RequireAuthorization(RbacPolicyConfiguration.CoordinatorPolicy);

app.MapPost("/api/admin/action", () => Results.Ok())
    .RequireAuthorization(RbacPolicyConfiguration.AdminPolicy);
```

## Testing

### Unit Testing with Mocked Users

```csharp
using System.Security.Claims;
using Innov.Lib.Rbac;

var claims = new[]
{
    new Claim(ClaimTypes.Role, RbacRoles.Coordinator),
    new Claim("preferred_username", "test@example.com")
};
var identity = new ClaimsIdentity(claims, "TestAuth");
var user = new ClaimsPrincipal(identity);

Assert.True(user.IsCoordinator());
Assert.False(user.IsAdmin());
```

### Integration Testing

Use `WebApplicationFactory` with `WithWebHostBuilder` to configure test authentication:

```csharp
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

var factory = new WebApplicationFactory<Program>()
    .WithWebHostBuilder(builder =>
    {
        builder.ConfigureServices(services =>
        {
            services.AddAuthentication("Test")
                .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>("Test", options => { });
        });
    });

var client = factory.CreateClient();
```

## Troubleshooting

### 401 Unauthorized

- Verify JWT token is valid and not expired
- Check `appsettings.json` has correct `TenantId` and `ClientId`
- Verify token audience matches your `ClientId`

### 403 Forbidden

- Check user has required role assigned in Azure AD
- Verify role claim is present in token (use jwt.ms to decode)
- Confirm middleware is registered AFTER authentication

### Roles Not Working

- Verify `UseRbacMiddleware()` is called between `UseAuthentication()` and `UseAuthorization()`
- Check Azure AD token includes `roles` claim
- Ensure App Roles are properly configured in Azure AD App Registration

### Multiple Role Values Not Recognized

The middleware handles both:
- Single role as string: `"roles": "Admin"`
- Multiple roles as array: `"roles": ["Admin", "Supervisor"]`
- Comma-separated string: `"roles": "Admin,Supervisor"`

If roles still aren't recognized, check the raw JWT token structure.

## Migration from Existing RBAC

If you have existing authorization code:

### Before (manual role checking)

```csharp
[Authorize]
public IActionResult MyAction()
{
    if (!User.IsInRole("Admin") && !User.IsInRole("Supervisor"))
    {
        return Forbid();
    }
    // ...
}
```

### After (declarative RBAC)

```csharp
[RequireRole(RbacRoles.Supervisor, RbacRoles.Admin)]
public IActionResult MyAction()
{
    // Authorization handled automatically
}
```

## Best Practices

1. **Always use constants** from `RbacRoles` instead of string literals
2. **Order matters**: Authentication → RBAC Middleware → Authorization
3. **Test role hierarchies**: Verify higher roles can access lower-level endpoints
4. **Use policies for minimal APIs**: More readable than inline role checks
5. **Log authorization failures**: Add custom auth failure handler if needed

## Additional Resources

- [Azure AD App Roles Documentation](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-add-app-roles-in-azure-ad-apps)
- [ASP.NET Core Authorization](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/introduction)
- [JWT.io Token Decoder](https://jwt.io/)
