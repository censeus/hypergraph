"""Models module with class inheritance examples."""


class BaseModel:
    """A base model for all entities."""

    def save(self):
        """Save the model to storage."""
        pass


class User(BaseModel):
    """A user in the system."""

    def __init__(self, name: str, email: str):
        """Initialize a user with a name and email."""
        self.name = name
        self.email = email

    def greet(self) -> str:
        """Return a greeting string."""
        return f"Hello, {self.name}!"


class AdminUser(User):
    """An admin user with elevated privileges."""

    def __init__(self, name: str, email: str, role: str = "admin"):
        super().__init__(name, email)
        self.role = role

    def promote(self, user: User) -> None:
        """Promote a regular user to admin."""
        pass
