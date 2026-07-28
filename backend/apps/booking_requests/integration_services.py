import hashlib
import json
import secrets
from datetime import date, datetime
from typing import Any

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.booking_requests.authentication import (
    BookingRequestCredentialAuth,
    booking_request_api_token_digest,
)
from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestApiCredential,
    BookingRequestSubmission,
)
from apps.booking_requests.services import create_booking_request
from config.api.exceptions import ApiProblem


def credential_metadata(credential: BookingRequestApiCredential) -> dict[str, Any]:
    return {
        "is_configured": credential.is_configured,
        "token_hint": credential.token_hint,
        "rotated_at": credential.rotated_at,
        "rotated_by_display_name": credential.rotated_by_display_name,
        "version": credential.version,
    }


def _booking_request_api_credential_for_update() -> BookingRequestApiCredential:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [1_009_001])
    BookingRequestApiCredential.objects.get_or_create(pk=BookingRequestApiCredential.SINGLETON_ID)
    return BookingRequestApiCredential.objects.select_for_update().get(
        pk=BookingRequestApiCredential.SINGLETON_ID
    )


@transaction.atomic
def rotate_booking_request_api_token(
    *,
    actor: User,
    requested_version: int,
    correlation_id: str,
) -> tuple[BookingRequestApiCredential, str]:
    credential = _booking_request_api_credential_for_update()
    if credential.version != requested_version:
        raise ApiProblem(
            code="version_conflict",
            message="Токен уже змінено в іншій сесії. Оновіть дані й повторіть дію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія налаштування застаріла."]},
        )

    before = credential_metadata(credential)
    token = f"podo_br_{secrets.token_urlsafe(32)}"
    credential.token_digest = booking_request_api_token_digest(token)
    credential.token_hint = token[-6:]
    credential.rotated_by = actor
    credential.rotated_by_display_name = actor.display_name
    credential.rotated_at = timezone.now()
    credential.version += 1
    credential.save(
        update_fields=(
            "token_digest",
            "token_hint",
            "rotated_by",
            "rotated_by_display_name",
            "rotated_at",
            "version",
            "updated_at",
        )
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.BOOKING_REQUEST_API_TOKEN_ROTATED,
        object_type="booking_request_api_credential",
        object_id=credential.pk,
        object_label="API заявок",
        correlation_id=correlation_id,
        before=before,
        after=credential_metadata(credential),
        description="Згенеровано новий API-токен для заявок.",
    )
    return credential, token


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported canonical payload value: {type(value).__name__}")


def canonical_booking_request_payload_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


@transaction.atomic
def create_external_booking_request(
    *,
    data: dict[str, Any],
    idempotency_key: str,
    auth: BookingRequestCredentialAuth,
    correlation_id: str,
) -> tuple[BookingRequest, bool]:
    credential = BookingRequestApiCredential.objects.select_for_update().get(pk=auth.credential_id)
    supplied_digest = booking_request_api_token_digest(auth.token)
    if (
        not credential.is_configured
        or credential.version != auth.credential_version
        or not secrets.compare_digest(credential.token_digest, supplied_digest)
    ):
        raise ApiProblem(
            code="invalid_bearer_token",
            message="Bearer token відсутній або недійсний.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload_hash = canonical_booking_request_payload_hash(data)
    existing = (
        BookingRequestSubmission.objects.select_related("booking_request")
        .filter(credential=credential, idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        if not secrets.compare_digest(existing.payload_hash, payload_hash):
            raise ApiProblem(
                code="idempotency_payload_mismatch",
                message="Idempotency-Key уже використано з іншими даними.",
                status_code=status.HTTP_409_CONFLICT,
                fields={"idempotency_key": ["Використайте новий ключ для змінених даних."]},
            )
        return existing.booking_request, True

    item = create_booking_request(data=data, correlation_id=correlation_id)
    BookingRequestSubmission.objects.create(
        credential=credential,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        booking_request=item,
    )
    return item, False
