"""
Role constants and hierarchy logic for RBAC.

Extracted from RPA Task Tracker backend (D:/repos/RPA.TaskTracker.UX/backend/app/core/roles.py)
and adapted for library use. Implements three-tier role hierarchy where Admin can access all
resources, Supervisor can access Supervisor/Coordinator resources, and Coordinator is the base
authenticated-user role.
"""

from typing import Any


# Role constants matching Entra ID role claim values
ROLE_ADMIN = "Admin"
ROLE_SUPERVISOR = "Supervisor"
ROLE_COORDINATOR = "Coordinator"


class RbacRoles:
    """
    Role constants with hierarchical access control logic.
    
    Hierarchy (high to low privilege):
      Admin > Supervisor > Coordinator
    
    An Admin can access any resource requiring Supervisor or Coordinator.
    A Supervisor can access any resource requiring Coordinator.
    A Coordinator can only access Coordinator-level resources.
    """
    
    ADMIN = ROLE_ADMIN
    SUPERVISOR = ROLE_SUPERVISOR
    COORDINATOR = ROLE_COORDINATOR
    
    @staticmethod
    def check_role(user: dict[str, Any], required_role: str) -> bool:
        """
        Check if user has the required role or a higher-privilege role.
        
        Args:
            user: User dict with "roles" key containing a list of role strings
            required_role: The minimum role required (e.g., ROLE_COORDINATOR)
            
        Returns:
            True if user's roles satisfy the requirement, False otherwise
            
        Example:
            user = {"email": "admin@dcli.com", "roles": ["Admin"]}
            RbacRoles.check_role(user, ROLE_COORDINATOR)  # True (Admin > Coordinator)
            RbacRoles.check_role(user, ROLE_ADMIN)  # True (exact match)
        """
        user_roles = set(user.get("roles", []))
        
        if required_role == ROLE_COORDINATOR:
            allowed = {ROLE_COORDINATOR, ROLE_SUPERVISOR, ROLE_ADMIN}
        elif required_role == ROLE_SUPERVISOR:
            allowed = {ROLE_SUPERVISOR, ROLE_ADMIN}
        elif required_role == ROLE_ADMIN:
            allowed = {ROLE_ADMIN}
        else:
            # Unknown role requirement — deny by default
            return False
        
        return bool(allowed.intersection(user_roles))
