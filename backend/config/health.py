import logging
from collections.abc import Callable
from urllib.request import urlopen

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from redis import Redis

logger = logging.getLogger("podoria.health")


def check_database() -> None:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def check_redis() -> None:
    client = Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    client.ping()


def check_object_storage() -> None:
    with urlopen(settings.MINIO_HEALTH_URL, timeout=2) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError("object storage health endpoint is unavailable")


DEPENDENCY_CHECKS: dict[str, Callable[[], None]] = {
    "database": check_database,
    "redis": check_redis,
    "object_storage": check_object_storage,
}


@require_GET
def liveness(_request):
    return JsonResponse({"status": "ok", "service": "backend"})


@require_GET
def readiness(request):
    checks: dict[str, str] = {}

    for name, check in DEPENDENCY_CHECKS.items():
        try:
            check()
        except Exception:
            checks[name] = "unavailable"
            logger.warning(
                "dependency check failed",
                extra={"dependency": name, "request_id": request.request_id},
                exc_info=True,
            )
        else:
            checks[name] = "ok"

    is_ready = all(status == "ok" for status in checks.values())
    return JsonResponse(
        {
            "status": "ready" if is_ready else "unavailable",
            "service": "backend",
            "checks": checks,
        },
        status=200 if is_ready else 503,
    )
