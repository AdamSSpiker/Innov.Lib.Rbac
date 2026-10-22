"""Tests for RBAC roles, dependencies, and hierarchy."""

from typing import Any

import pytest
from fastapi import HTTPException

from innov_lib_rbac import (
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_SUPERVISOR,
    InsufficientRoleException,
    RbacRoles,
    check_role,
    require_admin,
    require_coordinator,
    require_supervisor,
)


class TestRbacRoles:
    """Tests for RbacRoles constants and check_role logic."""

    def test_role_constants(self):
        """Test that role constants have correct values."""
        assert RbacRoles.ADMIN == "Admin"
        assert RbacRoles.SUPERVISOR == "Supervisor"
        assert RbacRoles.COORDINATOR == "Coordinator"
        assert ROLE_ADMIN == "Admin"
        assert ROLE_SUPERVISOR == "Supervisor"
        assert ROLE_COORDINATOR == "Coordinator"

    def test_check_role_same_role(self):
        """Test that users with exact role match pass the check."""
        admin = {"email": "admin@test.com", "roles": ["Admin"]}
        supervisor = {"email": "super@test.com", "roles": ["Supervisor"]}
        coordinator = {"email": "coord@test.com", "roles": ["Coordinator"]}

        assert RbacRoles.check_role(admin, ROLE_ADMIN) is True
        assert RbacRoles.check_role(supervisor, ROLE_SUPERVISOR) is True
        assert RbacRoles.check_role(coordinator, ROLE_COORDINATOR) is True

    def test_check_role_hierarchy_admin(self):
        """Test that Admin can access all lower levels."""
        admin = {"email": "admin@test.com", "roles": ["Admin"]}

        assert RbacRoles.check_role(admin, ROLE_ADMIN) is True
        assert RbacRoles.check_role(admin, ROLE_SUPERVISOR) is True
        assert RbacRoles.check_role(admin, ROLE_COORDINATOR) is True

    def test_check_role_hierarchy_supervisor(self):
        """Test that Supervisor can access Coordinator but not Admin."""
        supervisor = {"email": "super@test.com", "roles": ["Supervisor"]}

        assert RbacRoles.check_role(supervisor, ROLE_ADMIN) is False
        assert RbacRoles.check_role(supervisor, ROLE_SUPERVISOR) is True
        assert RbacRoles.check_role(supervisor, ROLE_COORDINATOR) is True

    def test_check_role_hierarchy_coordinator(self):
        """Test that Coordinator cannot access higher roles."""
        coordinator = {"email": "coord@test.com", "roles": ["Coordinator"]}

        assert RbacRoles.check_role(coordinator, ROLE_ADMIN) is False
        assert RbacRoles.check_role(coordinator, ROLE_SUPERVISOR) is False
        assert RbacRoles.check_role(coordinator, ROLE_COORDINATOR) is True

    def test_check_role_no_roles(self):
        """Test that users with no roles are denied all access."""
        no_roles = {"email": "none@test.com", "roles": []}

        assert RbacRoles.check_role(no_roles, ROLE_ADMIN) is False
        assert RbacRoles.check_role(no_roles, ROLE_SUPERVISOR) is False
        assert RbacRoles.check_role(no_roles, ROLE_COORDINATOR) is False

    def test_check_role_multiple_roles(self):
        """Test user with multiple roles (takes highest)."""
        multi = {"email": "multi@test.com", "roles": ["Coordinator", "Admin"]}

        # Should pass all checks since Admin is present
        assert RbacRoles.check_role(multi, ROLE_ADMIN) is True
        assert RbacRoles.check_role(multi, ROLE_SUPERVISOR) is True
        assert RbacRoles.check_role(multi, ROLE_COORDINATOR) is True

    def test_check_role_unknown_required(self):
        """Test that unknown required role denies by default."""
        admin = {"email": "admin@test.com", "roles": ["Admin"]}

        assert RbacRoles.check_role(admin, "UnknownRole") is False

    def test_check_role_missing_roles_key(self):
        """Test user dict without 'roles' key is treated as no roles."""
        no_roles_key: dict[str, Any] = {"email": "test@test.com"}

        assert RbacRoles.check_role(no_roles_key, ROLE_COORDINATOR) is False


class TestCheckRoleHelper:
    """Tests for the check_role helper function."""

    def test_check_role_helper(self, mock_admin_user, mock_coordinator_user):
        """Test that check_role helper works for endpoint logic."""
        assert check_role(mock_admin_user, ROLE_ADMIN) is True
        assert check_role(mock_admin_user, ROLE_COORDINATOR) is True
        assert check_role(mock_coordinator_user, ROLE_ADMIN) is False
        assert check_role(mock_coordinator_user, ROLE_COORDINATOR) is True


class TestRequireAdminDependency:
    """Tests for require_admin FastAPI dependency."""

    def test_allows_admin(self, mock_admin_user):
        """Test that require_admin allows Admin users."""
        result = require_admin(mock_admin_user)
        assert result == mock_admin_user

    def test_denies_supervisor(self, mock_supervisor_user):
        """Test that require_admin denies Supervisor users."""
        with pytest.raises(HTTPException) as exc_info:
            require_admin(mock_supervisor_user)
        assert exc_info.value.status_code == 403
        assert "Admin role required" in exc_info.value.detail

    def test_denies_coordinator(self, mock_coordinator_user):
        """Test that require_admin denies Coordinator users."""
        with pytest.raises(HTTPException) as exc_info:
            require_admin(mock_coordinator_user)
        assert exc_info.value.status_code == 403

    def test_denies_no_roles(self, mock_no_role_user):
        """Test that require_admin denies users with no roles."""
        with pytest.raises(HTTPException) as exc_info:
            require_admin(mock_no_role_user)
        assert exc_info.value.status_code == 403


class TestRequireSupervisorDependency:
    """Tests for require_supervisor FastAPI dependency."""

    def test_allows_admin(self, mock_admin_user):
        """Test that require_supervisor allows Admin users."""
        result = require_supervisor(mock_admin_user)
        assert result == mock_admin_user

    def test_allows_supervisor(self, mock_supervisor_user):
        """Test that require_supervisor allows Supervisor users."""
        result = require_supervisor(mock_supervisor_user)
        assert result == mock_supervisor_user

    def test_denies_coordinator(self, mock_coordinator_user):
        """Test that require_supervisor denies Coordinator users."""
        with pytest.raises(HTTPException) as exc_info:
            require_supervisor(mock_coordinator_user)
        assert exc_info.value.status_code == 403
        assert "Supervisor role required" in exc_info.value.detail

    def test_denies_no_roles(self, mock_no_role_user):
        """Test that require_supervisor denies users with no roles."""
        with pytest.raises(HTTPException) as exc_info:
            require_supervisor(mock_no_role_user)
        assert exc_info.value.status_code == 403


class TestRequireCoordinatorDependency:
    """Tests for require_coordinator FastAPI dependency."""

    def test_allows_admin(self, mock_admin_user):
        """Test that require_coordinator allows Admin users."""
        result = require_coordinator(mock_admin_user)
        assert result == mock_admin_user

    def test_allows_supervisor(self, mock_supervisor_user):
        """Test that require_coordinator allows Supervisor users."""
        result = require_coordinator(mock_supervisor_user)
        assert result == mock_supervisor_user

    def test_allows_coordinator(self, mock_coordinator_user):
        """Test that require_coordinator allows Coordinator users."""
        result = require_coordinator(mock_coordinator_user)
        assert result == mock_coordinator_user

    def test_denies_no_roles(self, mock_no_role_user):
        """Test that require_coordinator denies users with no roles."""
        with pytest.raises(HTTPException) as exc_info:
            require_coordinator(mock_no_role_user)
        assert exc_info.value.status_code == 403
        assert "Coordinator role required" in exc_info.value.detail

    def test_allows_multi_role_user(self, mock_multi_role_user):
        """Test that users with multiple roles are handled correctly."""
        result = require_coordinator(mock_multi_role_user)
        assert result == mock_multi_role_user


class TestInsufficientRoleException:
    """Tests for InsufficientRoleException."""

    def test_exception_defaults(self):
        """Test exception with default message."""
        exc = InsufficientRoleException()
        assert exc.status_code == 403
        assert "Insufficient role" in exc.detail

    def test_exception_custom_message(self):
        """Test exception with custom message."""
        exc = InsufficientRoleException(detail="Custom denial message")
        assert exc.status_code == 403
        assert exc.detail == "Custom denial message"

    def test_exception_is_http_exception(self):
        """Test that InsufficientRoleException is an HTTPException subclass."""
        exc = InsufficientRoleException()
        assert isinstance(exc, HTTPException)
