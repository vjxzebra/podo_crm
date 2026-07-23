import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.request import Request

from config.api.exceptions import ApiProblem

logger = logging.getLogger("podoria.security")


def _digest(value: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()


def _client_ip(request: Request) -> str:
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    forwarded = [
        item.strip()
        for item in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if item.strip()
    ]
    trusted_count = settings.LOGIN_RATE_LIMIT_TRUSTED_PROXY_COUNT
    if trusted_count > 0 and len(forwarded) >= trusted_count:
        return forwarded[-trusted_count]
    return remote_addr


def _bucket_key(*, kind: str, value: str, bucket: int) -> str:
    return f"podoria:login:{kind}:{_digest(value)}:{bucket}"


def _window() -> tuple[int, int]:
    now = int(time.time())
    window_seconds = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    return now // window_seconds, window_seconds - (now % window_seconds)


def _keys(request: Request, email: str) -> tuple[str, str, int]:
    bucket, retry_after = _window()
    normalized_email = email.strip().lower()
    return (
        _bucket_key(kind="email", value=normalized_email, bucket=bucket),
        _bucket_key(kind="ip", value=_client_ip(request), bucket=bucket),
        retry_after,
    )


def _security_unavailable() -> ApiProblem:
    return ApiProblem(
        code="login_security_unavailable",
        message="Вхід тимчасово недоступний. Спробуйте пізніше.",
        status_code=503,
    )


def _increment(key: str, timeout: int) -> int:
    if cache.add(key, 1, timeout=timeout):
        return 1
    return int(cache.incr(key))


def reserve_login_attempt(request: Request, email: str) -> None:
    email_key, ip_key, retry_after = _keys(request, email)
    try:
        email_attempts = _increment(email_key, retry_after)
        ip_attempts = _increment(ip_key, retry_after)
    except Exception as exc:
        logger.exception("login rate-limit cache unavailable")
        raise _security_unavailable() from exc
    if (
        email_attempts > settings.LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS
        or ip_attempts > settings.LOGIN_RATE_LIMIT_IP_ATTEMPTS
    ):
        raise ApiProblem(
            code="login_rate_limited",
            message="Забагато спроб входу. Зачекайте та спробуйте знову.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )


def clear_successful_login_attempt(request: Request, email: str) -> None:
    email_key, ip_key, _ = _keys(request, email)
    try:
        cache.delete(email_key)
        remaining_ip_attempts = cache.decr(ip_key)
        if remaining_ip_attempts <= 0:
            cache.delete(ip_key)
    except ValueError:
        return
    except Exception as exc:
        logger.exception("login rate-limit cache unavailable")
        raise _security_unavailable() from exc
