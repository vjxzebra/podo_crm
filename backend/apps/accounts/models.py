from typing import Any, ClassVar

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UserRole(models.TextChoices):
    PODOLOGIST = "podologist", "Подолог"
    RECEPTION = "reception", "Рецепція"
    ADMIN = "admin", "Адміністратор"


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    @staticmethod
    def normalize_login(email: str) -> str:
        return email.strip().lower()

    def get_by_natural_key(self, username: str | None) -> "User":
        if username is None:
            raise self.model.DoesNotExist
        return self.get(email__iexact=self.normalize_login(username))

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_login(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None  # type: ignore[assignment]
    email = models.EmailField("email", unique=True)
    role = models.CharField(max_length=20, choices=UserRole.choices)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()  # type: ignore[misc, assignment]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique")
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def display_name(self) -> str:
        full_name = self.get_full_name().strip()
        return full_name or self.email
