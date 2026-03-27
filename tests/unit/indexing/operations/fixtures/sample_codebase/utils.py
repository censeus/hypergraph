"""Utility functions with imports and decorators."""

import os
from functools import lru_cache

from . import models


def validate_email(email: str) -> bool:
    """Validate an email address format."""
    return "@" in email


@lru_cache(maxsize=128)
def get_user_by_name(name: str) -> "models.User":
    """Look up a user by name (cached)."""
    return models.User(name=name, email=f"{name}@example.com")


def create_admin(name: str) -> "models.AdminUser":
    """Create a new admin user."""
    email = f"{name}@admin.example.com"
    if not validate_email(email):
        raise ValueError("Invalid email")
    return models.AdminUser(name=name, email=email)
