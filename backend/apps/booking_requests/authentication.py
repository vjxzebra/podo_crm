import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.request import Request

from apps.booking_requests.integration_security import (
    reserve_invalid_booking_request_api_attempt,
    reserve_valid_booking_request_api_attempt,
)
from apps.booking_requests.models import BookingRequestApiCredential
from config.api.exceptions import ApiProblem


class BookingRequestIntegrationPrincipal:
    is_authenticated = True
    is_anonymous = False

    def __str__(self) -> str:
        return "booking-request-integration"


@dataclass(frozen=True)
class BookingRequestCredentialAuth:
    credential_id: int
    credential_version: int
    token: str

    def __repr__(self) -> str:
        return "BookingRequestCredentialAuth(token=[REDACTED])"


def booking_request_api_token_digest(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def _invalid_bearer_token(request: Request) -> ApiProblem:
    reserve_invalid_booking_request_api_attempt(request)
    return ApiProblem(
        code="invalid_bearer_token",
        message="Bearer token відсутній або недійсний.",
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


class BookingRequestBearerAuthentication(BaseAuthentication):
    def authenticate(
        self,
        request: Request,
    ) -> tuple[BookingRequestIntegrationPrincipal, BookingRequestCredentialAuth]:
        header = get_authorization_header(request).split()
        if len(header) != 2 or header[0].lower() != b"bearer":
            raise _invalid_bearer_token(request)
        try:
            token = header[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise _invalid_bearer_token(request) from exc
        if not token:
            raise _invalid_bearer_token(request)

        credential = BookingRequestApiCredential.objects.filter(
            pk=BookingRequestApiCredential.SINGLETON_ID
        ).first()
        expected_digest = credential.token_digest if credential is not None else "0" * 64
        supplied_digest = booking_request_api_token_digest(token)
        if (
            credential is None
            or not credential.is_configured
            or not secrets.compare_digest(expected_digest, supplied_digest)
        ):
            raise _invalid_bearer_token(request)

        reserve_valid_booking_request_api_attempt(request)
        return (
            BookingRequestIntegrationPrincipal(),
            BookingRequestCredentialAuth(
                credential_id=credential.pk,
                credential_version=credential.version,
                token=token,
            ),
        )

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"


class BookingRequestBearerAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.booking_requests.authentication.BookingRequestBearerAuthentication"
    name = "bookingRequestBearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "opaque",
        }
