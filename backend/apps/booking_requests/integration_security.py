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
    trusted_count = settings.BOOKING_REQUEST_API_TRUSTED_PROXY_COUNT
    if trusted_count > 0 and len(forwarded) >= trusted_count:
        return forwarded[-trusted_count]
    return remote_addr


def _window(window_seconds: int) -> tuple[int, int]:
    now = int(time.time())
    return now // window_seconds, window_seconds - (now % window_seconds)


def _increment(key: str, timeout: int) -> int:
    if cache.add(key, 1, timeout=timeout):
        return 1
    return int(cache.incr(key))


def _reserve(
    *,
    request: Request,
    kind: str,
    identity: str,
    attempts: int,
    window_seconds: int,
) -> None:
    bucket, retry_after = _window(window_seconds)
    key = f"podoria:booking-request-api:{kind}:{_digest(identity)}:{bucket}"
    try:
        current = _increment(key, retry_after)
    except Exception as exc:
        logger.exception("booking request API rate-limit cache unavailable")
        raise ApiProblem(
            code="service_unavailable",
            message="Сервіс тимчасово недоступний. Спробуйте пізніше.",
            status_code=503,
        ) from exc
    if current > attempts:
        raise ApiProblem(
            code="rate_limit_exceeded",
            message="Забагато запитів. Спробуйте пізніше.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )


def reserve_invalid_booking_request_api_attempt(request: Request) -> None:
    _reserve(
        request=request,
        kind="invalid-ip",
        identity=_client_ip(request),
        attempts=settings.BOOKING_REQUEST_API_INVALID_ATTEMPTS,
        window_seconds=settings.BOOKING_REQUEST_API_INVALID_WINDOW_SECONDS,
    )


def reserve_valid_booking_request_api_attempt(request: Request) -> None:
    _reserve(
        request=request,
        kind="valid-token",
        identity="singleton",
        attempts=settings.BOOKING_REQUEST_API_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.BOOKING_REQUEST_API_RATE_LIMIT_WINDOW_SECONDS,
    )
