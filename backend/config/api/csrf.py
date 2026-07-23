from django.http import HttpRequest, JsonResponse

from config.middleware import get_request_id


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    return JsonResponse(
        {
            "code": "csrf_failed",
            "message": (
                "Не вдалося підтвердити безпечність запиту. Оновіть сторінку й повторіть дію."
            ),
            "fields": {},
            "correlation_id": get_request_id(request),
        },
        status=403,
    )
