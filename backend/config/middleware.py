import logging
import re
from time import perf_counter
from uuid import uuid4

logger = logging.getLogger("podoria.request")
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id if VALID_REQUEST_ID.fullmatch(incoming_id) else str(uuid4())
        request.request_id = request_id
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
