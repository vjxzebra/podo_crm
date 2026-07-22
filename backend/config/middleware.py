import logging
import re
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.http.response import JsonResponse
from django.utils import timezone

from apps.accounts.session_security import (
    SESSION_ISSUED_AT_KEY,
    SESSION_LAST_SEEN_AT_KEY,
    initialize_session_security,
)

logger = logging.getLogger("podoria.request")
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def get_request_id(request: object) -> str:
    return str(getattr(request, "request_id", uuid4()))


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id if VALID_REQUEST_ID.fullmatch(incoming_id) else str(uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]
        started_at = perf_counter()

        response = self.get_response(request)
        response["X-Request-ID"] = request_id

        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return response


class SecurityHeadersMiddleware:
    """Apply the same browser boundary to direct API and proxied responses."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
        response["Permissions-Policy"] = settings.PERMISSIONS_POLICY
        if request.path.startswith("/api/v1/"):
            existing = response.get("Cache-Control", "")
            response["Cache-Control"] = "private, no-store" if "private" in existing else "no-store"
        return response


class SessionExpiryMiddleware:
    """Enforce idle and absolute server-side lifetime for authenticated API sessions."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith("/api/v1/") or not request.user.is_authenticated:
            return self.get_response(request)

        now = timezone.now().timestamp()
        issued_at = request.session.get(SESSION_ISSUED_AT_KEY)
        last_seen_at = request.session.get(SESSION_LAST_SEEN_AT_KEY)
        if not isinstance(issued_at, (int, float)) or not isinstance(last_seen_at, (int, float)):
            initialize_session_security(request)
            issued_at = now
            last_seen_at = now

        idle_expired = now - float(last_seen_at) >= settings.SESSION_IDLE_TIMEOUT_SECONDS
        absolute_expired = now - float(issued_at) >= settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS
        if idle_expired or absolute_expired:
            logout(request)
            response = JsonResponse(
                {
                    "code": "session_expired",
                    "message": "Сесію завершено. Увійдіть знову, щоб продовжити роботу.",
                    "fields": {},
                    "correlation_id": get_request_id(request),
                },
                status=401,
            )
            response["WWW-Authenticate"] = "Session"
            return response

        request.session[SESSION_LAST_SEEN_AT_KEY] = now
        return self.get_response(request)
