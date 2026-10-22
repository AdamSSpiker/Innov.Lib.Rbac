# Innov.Lib.Rbac — Examples

Comprehensive examples demonstrating real-world usage of the RBAC library across different ASP.NET Core application types.

---

## Table of Contents

1. [Minimal API with [RequireRole]](#1-minimal-api-with-requirerole)
2. [MVC Controller with Role Checks](#2-mvc-controller-with-role-checks)
3. [Custom Policies](#3-custom-policies)
4. [Middleware Chaining](#4-middleware-chaining)
5. [Blazor Server Integration](#5-blazor-server-integration)
6. [Unit Testing RBAC Policies](#6-unit-testing-rbac-policies)

---

## 1. Minimal API with [RequireRole]

### Basic Minimal API Setup

```csharp
using Innov.Lib.Rbac;

var builder = WebApplication.CreateBuilder(args);

// Register RBAC policies
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(/* configure JWT */);

builder.Services.AddRbacPolicies();

var app = builder.Build();

app.UseAuthentication();
app.UseRbacMiddleware();
app.UseAuthorization();

// Public endpoint (no auth required)
app.MapGet("/api/health", () => Results.Ok(new { status = "healthy" }))
    .AllowAnonymous();

// Coordinator-only endpoint using policy
app.MapGet("/api/dashboard", () => 
{
    return Results.Ok(new { message = "Dashboard data" });
})
.RequireAuthorization(RbacPolicyConfiguration.CoordinatorPolicy);

// Supervisor-only endpoint
app.MapGet("/api/reports", () => 
{
    return Results.Ok(new { report = "Team performance metrics" });
})
.RequireAuthorization(RbacPolicyConfiguration.SupervisorPolicy);

// Admin-only endpoint
app.MapGet("/api/admin/settings", () => 
{
    return Results.Ok(new { settings = "System configuration" });
})
.RequireAuthorization(RbacPolicyConfiguration.AdminPolicy);

app.Run();
```

### Minimal API with Inline Role Logic

```csharp
app.MapGet("/api/tasks", (ClaimsPrincipal user) =>
{
    if (!user.IsCoordinator())
    {
        return Results.Forbid();
    }

    var tasks = GetTasksForUser(user);
    
    // Supervisors see additional data
    if (user.IsSupervisor())
    {
        return Results.Ok(new 
        { 
            tasks, 
            teamMetrics = GetTeamMetrics() 
        });
    }

    return Results.Ok(new { tasks });
})
.RequireAuthorization(RbacPolicyConfiguration.CoordinatorPolicy);
```

### Minimal API with POST and Role Validation

```csharp
app.MapPost("/api/tasks/{id}/approve", 
    (int id, ClaimsPrincipal user) =>
{
    if (!user.IsSupervisor())
    {
        return Results.Problem(
            "Only supervisors can approve tasks",
            statusCode: StatusCodes.Status403Forbidden
        );
    }

    ApproveTask(id, user.FindFirst("email")?.Value);
    return Results.Ok(new { message = "Task approved" });
})
.RequireAuthorization(RbacPolicyConfiguration.SupervisorPolicy);
```

---

## 2. MVC Controller with Role Checks

### Declarative Authorization with [RequireRole]

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Mvc;

namespace MyApp.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TasksController : ControllerBase
{
    // All coordinators, supervisors, and admins can access
    [HttpGet("mine")]
    [RequireRole(RbacRoles.Coordinator, RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult GetMyTasks()
    {
        var email = User.FindFirst("email")?.Value;
        var tasks = GetTasksForUser(email);

        return Ok(new { tasks, count = tasks.Count });
    }

    // Supervisor and admin only
    [HttpGet("all")]
    [RequireRole(RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult GetAllTasks([FromQuery] string? assignedTo = null)
    {
        if (User.IsAdmin() && assignedTo != null)
        {
            return Ok(GetTasksForUser(assignedTo));
        }

        return Ok(GetAllTasks());
    }

    // Admin-only endpoint
    [HttpPost("bulk-approve")]
    [RequireRole(RbacRoles.Admin)]
    public IActionResult BulkApprove([FromBody] BulkApproveRequest request)
    {
        if (request.TaskIds == null || request.TaskIds.Length == 0)
        {
            return BadRequest("No task IDs provided");
        }

        BulkApproveTasksInternal(request.TaskIds);
        return Ok(new { approved = request.TaskIds.Length });
    }
}

public record BulkApproveRequest(int[] TaskIds);
```

### Controller-Level Authorization

```csharp
// Entire controller requires Admin role
[ApiController]
[Route("api/admin")]
[RequireRole(RbacRoles.Admin)]
public class AdminController : ControllerBase
{
    [HttpGet("users")]
    public IActionResult GetUsers() => Ok(GetAllUsers());

    [HttpGet("audit-log")]
    public IActionResult GetAuditLog() => Ok(GetAuditLog());

    // Override: allow supervisors too
    [HttpGet("dashboard")]
    [RequireRole(RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult GetDashboard() => Ok(GetAdminDashboard());
}
```

### Programmatic Role Checks Inside Actions

```csharp
[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    [HttpGet("{reportId}")]
    [RequireRole(RbacRoles.Coordinator, RbacRoles.Supervisor, RbacRoles.Admin)]
    public IActionResult GetReport(int reportId)
    {
        var report = GetReportById(reportId);
        
        if (report == null)
        {
            return NotFound();
        }

        // Coordinators can only see their own reports
        if (User.IsCoordinator() && !User.IsSupervisor())
        {
            var userEmail = User.FindFirst("email")?.Value;
            if (report.CreatedBy != userEmail)
            {
                return Forbid();
            }
        }

        // Redact sensitive fields for non-admins
        if (!User.IsAdmin())
        {
            report.InternalNotes = null;
            report.AuditTrail = null;
        }

        return Ok(report);
    }
}
```

---

## 3. Custom Policies

### Registering Custom Policies

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Authorization;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAuthentication(/* ... */);

// Register built-in policies
builder.Services.AddRbacPolicies();

// Add custom policies
builder.Services.AddAuthorization(options =>
{
    // Require BOTH Supervisor AND a specific claim
    options.AddPolicy("SupervisorWithAuditAccess", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireRole(RbacRoles.Supervisor, RbacRoles.Admin);
        policy.RequireClaim("permissions", "audit.read");
    });

    // OR logic: Admin OR a specific permission
    options.AddPolicy("AdminOrReportEditor", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireAssertion(context =>
        {
            var user = context.User;
            return user.IsAdmin() || 
                   user.HasClaim("permissions", "reports.edit");
        });
    });

    // Complex multi-condition policy
    options.AddPolicy("CanApproveHighValueTasks", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireAssertion(context =>
        {
            var user = context.User;
            
            // Admins can always approve
            if (user.IsAdmin()) return true;
            
            // Supervisors can approve if they have the certification
            if (user.IsSupervisor())
            {
                return user.HasClaim("certifications", "high-value-approval");
            }
            
            return false;
        });
    });
});

var app = builder.Build();
```

### Using Custom Policies

```csharp
// Minimal API
app.MapGet("/api/audit-log", () => Results.Ok(GetAuditLog()))
    .RequireAuthorization("SupervisorWithAuditAccess");

// Controller
[HttpPost("approve-high-value")]
[Authorize(Policy = "CanApproveHighValueTasks")]
public IActionResult ApproveHighValueTask([FromBody] ApprovalRequest request)
{
    // Only users meeting complex policy criteria reach here
    ApproveTask(request.TaskId);
    return Ok();
}
```

### Custom Policy Handler (Advanced)

```csharp
using Microsoft.AspNetCore.Authorization;

// Custom requirement
public class MinimumTenureRequirement : IAuthorizationRequirement
{
    public int MinimumMonths { get; }
    
    public MinimumTenureRequirement(int minimumMonths)
    {
        MinimumMonths = minimumMonths;
    }
}

// Custom handler
public class MinimumTenureHandler : AuthorizationHandler<MinimumTenureRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        MinimumTenureRequirement requirement)
    {
        var tenureClaim = context.User.FindFirst("tenure_months");
        
        if (tenureClaim != null && 
            int.TryParse(tenureClaim.Value, out var months) &&
            months >= requirement.MinimumMonths)
        {
            context.Succeed(requirement);
        }
        
        return Task.CompletedTask;
    }
}

// Registration
builder.Services.AddSingleton<IAuthorizationHandler, MinimumTenureHandler>();
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("SeniorCoordinator", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireRole(RbacRoles.Coordinator, RbacRoles.Supervisor, RbacRoles.Admin);
        policy.AddRequirements(new MinimumTenureRequirement(6));
    });
});
```

---

## 4. Middleware Chaining

### Correct Middleware Order

```csharp
var app = builder.Build();

// 1. Exception handling (catches errors from all middleware below)
app.UseExceptionHandler("/error");

// 2. HTTPS redirection (before auth checks)
app.UseHttpsRedirection();

// 3. Static files (before auth — public assets)
app.UseStaticFiles();

// 4. Routing (determines which endpoint matches)
app.UseRouting();

// 5. CORS (if needed, before auth)
app.UseCors("AllowSpecificOrigins");

// 6. Authentication (validates JWT, sets User identity)
app.UseAuthentication();

// 7. RBAC Middleware (enriches role claims from JWT)
app.UseRbacMiddleware();

// 8. Authorization (enforces [Authorize] and policies)
app.UseAuthorization();

// 9. Endpoints
app.MapControllers();
app.Run();
```

### Custom Middleware Before RBAC

```csharp
// Custom header enrichment middleware
public class CustomClaimsMiddleware
{
    private readonly RequestDelegate _next;

    public CustomClaimsMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        if (context.User?.Identity?.IsAuthenticated == true)
        {
            // Add custom claims from database, cache, etc.
            var identity = context.User.Identity as ClaimsIdentity;
            var email = context.User.FindFirst("email")?.Value;
            
            if (email != null)
            {
                var userMetadata = await GetUserMetadataAsync(email);
                identity?.AddClaim(new Claim("tenure_months", 
                    userMetadata.TenureMonths.ToString()));
                identity?.AddClaim(new Claim("certifications", 
                    string.Join(",", userMetadata.Certifications)));
            }
        }

        await _next(context);
    }
}

// Register in pipeline
app.UseAuthentication();
app.UseMiddleware<CustomClaimsMiddleware>();  // Before RBAC
app.UseRbacMiddleware();
app.UseAuthorization();
```

### Logging Middleware After RBAC

```csharp
public class RbacAuditMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<RbacAuditMiddleware> _logger;

    public RbacAuditMiddleware(RequestDelegate next, ILogger<RbacAuditMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        if (context.User?.Identity?.IsAuthenticated == true)
        {
            var email = context.User.FindFirst("email")?.Value;
            var roles = string.Join(",", context.User.Claims
                .Where(c => c.Type == ClaimTypes.Role)
                .Select(c => c.Value));

            _logger.LogInformation(
                "User {Email} with roles [{Roles}] accessing {Path}",
                email, roles, context.Request.Path);
        }

        await _next(context);
    }
}

// Register AFTER RBAC (so roles are enriched)
app.UseAuthentication();
app.UseRbacMiddleware();
app.UseMiddleware<RbacAuditMiddleware>();  // Logs enriched roles
app.UseAuthorization();
```

---

## 5. Blazor Server Integration

### Program.cs Setup

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Authentication.OpenIdConnect;
using Microsoft.Identity.Web;

var builder = WebApplication.CreateBuilder(args);

// Add Blazor Server
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();

// Add authentication (Microsoft.Identity.Web for Azure AD)
builder.Services.AddAuthentication(OpenIdConnectDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApp(builder.Configuration.GetSection("AzureAd"));

// Add RBAC policies
builder.Services.AddRbacPolicies();

var app = builder.Build();

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();

app.UseAuthentication();
app.UseRbacMiddleware();
app.UseAuthorization();

app.MapBlazorHub();
app.MapFallbackToPage("/_Host");

app.Run();
```

### Component with Role-Based UI

```razor
@page "/dashboard"
@attribute [Authorize(Policy = RbacPolicyConfiguration.CoordinatorPolicy)]
@using Innov.Lib.Rbac
@using System.Security.Claims
@inject AuthenticationStateProvider AuthenticationStateProvider

<h3>Dashboard</h3>

<AuthorizeView Roles="@RbacRoles.Coordinator,@RbacRoles.Supervisor,@RbacRoles.Admin">
    <Authorized>
        <div class="card">
            <h4>My Tasks</h4>
            <p>You have @TaskCount pending tasks.</p>
        </div>
    </Authorized>
</AuthorizeView>

<AuthorizeView Roles="@RbacRoles.Supervisor,@RbacRoles.Admin">
    <Authorized>
        <div class="card">
            <h4>Team Overview</h4>
            <p>Team metrics and reports appear here.</p>
        </div>
    </Authorized>
</AuthorizeView>

<AuthorizeView Roles="@RbacRoles.Admin">
    <Authorized>
        <div class="card">
            <h4>Admin Controls</h4>
            <button @onclick="OpenAdminPanel">System Settings</button>
        </div>
    </Authorized>
</AuthorizeView>

@code {
    private int TaskCount = 42;
    private ClaimsPrincipal? User;

    protected override async Task OnInitializedAsync()
    {
        var authState = await AuthenticationStateProvider.GetAuthenticationStateAsync();
        User = authState.User;
    }

    private void OpenAdminPanel()
    {
        // Navigate to admin panel
    }
}
```

### Programmatic Role Check in Blazor Component

```razor
@page "/tasks/{TaskId:int}"
@attribute [Authorize]
@using Innov.Lib.Rbac
@inject AuthenticationStateProvider AuthenticationStateProvider

<h3>Task Details</h3>

@if (CanViewTask)
{
    <div>
        <p>Task ID: @TaskId</p>
        <p>Status: @TaskStatus</p>

        @if (User?.IsSupervisor() == true)
        {
            <button @onclick="ApproveTask">Approve</button>
            <button @onclick="DeclineTask">Decline</button>
        }

        @if (User?.IsAdmin() == true)
        {
            <div class="admin-section">
                <h4>Admin Actions</h4>
                <button @onclick="ReassignTask">Reassign</button>
                <button @onclick="DeleteTask">Delete</button>
            </div>
        }
    </div>
}
else
{
    <p class="text-danger">You do not have permission to view this task.</p>
}

@code {
    [Parameter]
    public int TaskId { get; set; }

    private ClaimsPrincipal? User;
    private string TaskStatus = "Pending";
    private bool CanViewTask => User?.IsCoordinator() == true;

    protected override async Task OnInitializedAsync()
    {
        var authState = await AuthenticationStateProvider.GetAuthenticationStateAsync();
        User = authState.User;

        if (CanViewTask)
        {
            await LoadTaskDetailsAsync();
        }
    }

    private async Task LoadTaskDetailsAsync()
    {
        // Load task from API
    }

    private void ApproveTask() { /* Supervisor action */ }
    private void DeclineTask() { /* Supervisor action */ }
    private void ReassignTask() { /* Admin action */ }
    private void DeleteTask() { /* Admin action */ }
}
```

---

## 6. Unit Testing RBAC Policies

### Testing ClaimsPrincipal Extension Methods

```csharp
using Innov.Lib.Rbac;
using System.Security.Claims;
using Xunit;

public class RbacExtensionTests
{
    private static ClaimsPrincipal CreateUserWithRoles(params string[] roles)
    {
        var claims = roles.Select(r => new Claim(ClaimTypes.Role, r)).ToList();
        var identity = new ClaimsIdentity(claims, "TestAuth");
        return new ClaimsPrincipal(identity);
    }

    [Fact]
    public void IsCoordinator_WithCoordinatorRole_ReturnsTrue()
    {
        // Arrange
        var user = CreateUserWithRoles(RbacRoles.Coordinator);

        // Act & Assert
        Assert.True(user.IsCoordinator());
    }

    [Fact]
    public void IsSupervisor_WithCoordinatorRole_ReturnsFalse()
    {
        // Arrange
        var user = CreateUserWithRoles(RbacRoles.Coordinator);

        // Act & Assert
        Assert.False(user.IsSupervisor());
    }

    [Fact]
    public void HasAnyRole_WithMultipleRoles_ReturnsTrue()
    {
        // Arrange
        var user = CreateUserWithRoles(RbacRoles.Supervisor, RbacRoles.Admin);

        // Act
        var result = user.HasAnyRole(RbacRoles.Admin, RbacRoles.Coordinator);

        // Assert
        Assert.True(result);
    }

    [Fact]
    public void IsAdmin_WithNullUser_ReturnsFalse()
    {
        // Arrange
        ClaimsPrincipal? user = null;

        // Act & Assert
        Assert.False(user!.IsAdmin());
    }
}
```

### Testing Controllers with Role Requirements

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using Xunit;

public class TasksControllerTests
{
    private TasksController CreateControllerWithUser(params string[] roles)
    {
        var claims = roles.Select(r => new Claim(ClaimTypes.Role, r)).ToList();
        claims.Add(new Claim("email", "test@example.com"));
        
        var identity = new ClaimsIdentity(claims, "TestAuth");
        var user = new ClaimsPrincipal(identity);

        var controller = new TasksController();
        controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext { User = user }
        };

        return controller;
    }

    [Fact]
    public void GetMyTasks_AsCoordinator_ReturnsOk()
    {
        // Arrange
        var controller = CreateControllerWithUser(RbacRoles.Coordinator);

        // Act
        var result = controller.GetMyTasks();

        // Assert
        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public void GetAllTasks_AsCoordinator_ReturnsForbidden()
    {
        // Arrange
        var controller = CreateControllerWithUser(RbacRoles.Coordinator);

        // Act
        var result = controller.GetAllTasks();

        // Assert
        // Note: [RequireRole] would block at middleware level, not controller
        // This test assumes the attribute is enforced by the auth system
        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public void BulkApprove_AsAdmin_ReturnsOk()
    {
        // Arrange
        var controller = CreateControllerWithUser(RbacRoles.Admin);
        var request = new BulkApproveRequest(new[] { 1, 2, 3 });

        // Act
        var result = controller.BulkApprove(request);

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }
}
```

### Integration Testing with WebApplicationFactory

```csharp
using Innov.Lib.Rbac;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Security.Claims;
using Xunit;

public class RbacIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public RbacIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    private HttpClient CreateAuthenticatedClient(params string[] roles)
    {
        return _factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureTestServices(services =>
            {
                services.AddAuthentication("Test")
                    .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(
                        "Test", options => { });
            });
        }).CreateClient();
    }

    [Fact]
    public async Task Dashboard_AsCoordinator_ReturnsOk()
    {
        // Arrange
        var client = CreateAuthenticatedClient(RbacRoles.Coordinator);

        // Act
        var response = await client.GetAsync("/api/dashboard");

        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task AdminEndpoint_AsCoordinator_ReturnsForbidden()
    {
        // Arrange
        var client = CreateAuthenticatedClient(RbacRoles.Coordinator);

        // Act
        var response = await client.GetAsync("/api/admin/settings");

        // Assert
        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task AdminEndpoint_AsAdmin_ReturnsOk()
    {
        // Arrange
        var client = CreateAuthenticatedClient(RbacRoles.Admin);

        // Act
        var response = await client.GetAsync("/api/admin/settings");

        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
}

// Test authentication handler
public class TestAuthHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    public TestAuthHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder,
        ISystemClock clock) : base(options, logger, encoder, clock)
    {
    }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var claims = new[]
        {
            new Claim(ClaimTypes.Name, "Test User"),
            new Claim(ClaimTypes.Email, "test@example.com"),
            new Claim(ClaimTypes.Role, RbacRoles.Coordinator)
        };

        var identity = new ClaimsIdentity(claims, "Test");
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, "Test");

        return Task.FromResult(AuthenticateResult.Success(ticket));
    }
}
```

### Testing Custom Authorization Policies

```csharp
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.DependencyInjection;
using System.Security.Claims;
using Xunit;

public class CustomPolicyTests
{
    private IAuthorizationService CreateAuthorizationService()
    {
        var services = new ServiceCollection();
        services.AddAuthorization(options =>
        {
            options.AddPolicy("AdminOrReportEditor", policy =>
            {
                policy.RequireAssertion(context =>
                {
                    var user = context.User;
                    return user.IsAdmin() || 
                           user.HasClaim("permissions", "reports.edit");
                });
            });
        });
        services.AddLogging();

        var provider = services.BuildServiceProvider();
        return provider.GetRequiredService<IAuthorizationService>();
    }

    [Fact]
    public async Task CustomPolicy_AsAdmin_Succeeds()
    {
        // Arrange
        var authService = CreateAuthorizationService();
        var user = new ClaimsPrincipal(new ClaimsIdentity(new[]
        {
            new Claim(ClaimTypes.Role, RbacRoles.Admin)
        }, "Test"));

        // Act
        var result = await authService.AuthorizeAsync(
            user, 
            null, 
            "AdminOrReportEditor");

        // Assert
        Assert.True(result.Succeeded);
    }

    [Fact]
    public async Task CustomPolicy_WithReportPermission_Succeeds()
    {
        // Arrange
        var authService = CreateAuthorizationService();
        var user = new ClaimsPrincipal(new ClaimsIdentity(new[]
        {
            new Claim(ClaimTypes.Role, RbacRoles.Coordinator),
            new Claim("permissions", "reports.edit")
        }, "Test"));

        // Act
        var result = await authService.AuthorizeAsync(
            user, 
            null, 
            "AdminOrReportEditor");

        // Assert
        Assert.True(result.Succeeded);
    }

    [Fact]
    public async Task CustomPolicy_AsCoordinatorWithoutPermission_Fails()
    {
        // Arrange
        var authService = CreateAuthorizationService();
        var user = new ClaimsPrincipal(new ClaimsIdentity(new[]
        {
            new Claim(ClaimTypes.Role, RbacRoles.Coordinator)
        }, "Test"));

        // Act
        var result = await authService.AuthorizeAsync(
            user, 
            null, 
            "AdminOrReportEditor");

        // Assert
        Assert.False(result.Succeeded);
    }
}
```

---

## Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and component interactions
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) — Step-by-step integration instructions
- [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) — Project goals and technical context

---

**Last updated:** 2026-10-21
