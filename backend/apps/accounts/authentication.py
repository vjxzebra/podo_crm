from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import (
    SessionAuthentication as DRFSessionAuthentication,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from apps.accounts.models import User

FORCED_PASSWORD_ALLOWED_REQUESTS = frozenset(
    {
        ("GET", "/api/v1/session"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/first-login-password"),
        ("POST", "/api/v1/password-reset-requests"),
    }
)


class SessionAuthentication(DRFSessionAuthentication):
    """Session auth that correctly advertises missing credentials as HTTP 401."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"

    def authenticate(self, request: Request) -> tuple[User, None] | None:
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None
        user, auth = authenticated
        if (
            isinstance(user, User)
            and user.must_change_password
            and (request.method, request.path) not in FORCED_PASSWORD_ALLOWED_REQUESTS
        ):
            raise PermissionDenied("Перед продовженням роботи створіть власний пароль.")
        return user, auth


class SessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.SessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
