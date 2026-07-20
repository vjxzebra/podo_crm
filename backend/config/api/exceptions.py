import logging
from collections.abc import Mapping, Sequence
from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from config.middleware import get_request_id

logger = logging.getLogger("podoria.api")

STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "authentication_required",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
}

STATUS_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "Некоректний запит.",
    status.HTTP_401_UNAUTHORIZED: "Потрібна автентифікація.",
    status.HTTP_403_FORBIDDEN: "Недостатньо прав для цієї дії.",
    status.HTTP_404_NOT_FOUND: "Ресурс не знайдено.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "HTTP-метод не підтримується.",
    status.HTTP_409_CONFLICT: "Запит конфліктує з поточним станом ресурсу.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Забагато запитів. Спробуйте пізніше.",
}


class ApiProblem(APIException):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        fields: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.problem_code = code
        self.problem_message = message
        self.problem_fields = {
            key: [str(item) for item in values] for key, values in (fields or {}).items()
        }
        super().__init__(detail=message, code=code)


def _collect_field_errors(value: Any, path: str = "") -> dict[str, list[str]]:
    if isinstance(value, Mapping):
        collected: dict[str, list[str]] = {}
        for key, nested in value.items():
            nested_path = f"{path}.{key}" if path else str(key)
            for field, field_messages in _collect_field_errors(nested, nested_path).items():
                collected.setdefault(field, []).extend(field_messages)
        return collected

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        scalar_messages: list[str] = []
        collected = {}
        for index, nested in enumerate(value):
            if isinstance(nested, Mapping) or (
                isinstance(nested, Sequence) and not isinstance(nested, (str, bytes))
            ):
                nested_path = f"{path}.{index}" if path else str(index)
                for field, nested_messages in _collect_field_errors(nested, nested_path).items():
                    collected.setdefault(field, []).extend(nested_messages)
            else:
                scalar_messages.append(str(nested))
        if scalar_messages:
            collected.setdefault(path or "non_field_errors", []).extend(scalar_messages)
        return collected

    return {path or "non_field_errors": [str(value)]}


def api_exception_handler(exc: Exception, context: Mapping[str, Any]) -> Response:
    request = context.get("request")
    correlation_id = get_request_id(request) if request is not None else "unavailable"

    if isinstance(exc, ApiProblem):
        return Response(
            {
                "code": exc.problem_code,
                "message": exc.problem_message,
                "fields": exc.problem_fields,
                "correlation_id": correlation_id,
            },
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, dict(context))
    if response is None:
        logger.exception(
            "unhandled API exception",
            extra={"request_id": correlation_id},
            exc_info=exc,
        )
        return Response(
            {
                "code": "internal_error",
                "message": "Внутрішня помилка сервера.",
                "fields": {},
                "correlation_id": correlation_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ValidationError):
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        code = "validation_error"
        message = "Дані запиту не пройшли перевірку."
        fields = _collect_field_errors(response.data)
    else:
        code = STATUS_CODES.get(response.status_code, "api_error")
        message = STATUS_MESSAGES.get(response.status_code, "Не вдалося виконати запит.")
        fields = {}

    response.data = {
        "code": code,
        "message": message,
        "fields": fields,
        "correlation_id": correlation_id,
    }
    return response
