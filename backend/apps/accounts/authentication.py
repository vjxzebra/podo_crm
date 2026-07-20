from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication
from rest_framework.request import Request


class SessionAuthentication(DRFSessionAuthentication):
    """Session auth that correctly advertises missing credentials as HTTP 401."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"


class SessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.SessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
