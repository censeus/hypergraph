"""API service module with cross-module imports and function calls."""

from ..models import User
from ..utils import validate_email


def register_user(name: str, email: str) -> User:
    """Register a new user after validation."""
    if not validate_email(email):
        raise ValueError("Invalid email")
    user = User(name=name, email=email)
    user.save()
    return user
