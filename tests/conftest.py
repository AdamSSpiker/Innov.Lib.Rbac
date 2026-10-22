"""Pytest configuration and shared fixtures."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a FastAPI app instance for testing."""
    return FastAPI()


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_admin_user() -> dict[str, Any]:
    """Create a mock admin user (dict format matching Task Tracker)."""
    return {
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": ["Admin"],
    }


@pytest.fixture
def mock_supervisor_user() -> dict[str, Any]:
    """Create a mock supervisor user (dict format matching Task Tracker)."""
    return {
        "email": "supervisor@example.com",
        "name": "Supervisor User",
        "roles": ["Supervisor"],
    }


@pytest.fixture
def mock_coordinator_user() -> dict[str, Any]:
    """Create a mock coordinator user (dict format matching Task Tracker)."""
    return {
        "email": "coordinator@example.com",
        "name": "Coordinator User",
        "roles": ["Coordinator"],
    }


@pytest.fixture
def mock_no_role_user() -> dict[str, Any]:
    """Create a mock user with no roles."""
    return {
        "email": "norole@example.com",
        "name": "No Role User",
        "roles": [],
    }


@pytest.fixture
def mock_multi_role_user() -> dict[str, Any]:
    """Create a mock user with multiple roles (edge case testing)."""
    return {
        "email": "multi@example.com",
        "name": "Multi Role User",
        "roles": ["Coordinator", "Supervisor"],
    }
