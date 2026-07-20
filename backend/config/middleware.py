import logging
import re
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

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
