from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.audit.registry import EVENT_SECTIONS, AuditAction

REDACTED = "[REDACTED]"
SENSITIVE_KEY_SUFFIXES = (
    "password",
    "passwordhash",
    "token",
    "secret",
    "sessionid",
    "sessionkey",
    "signedurl",
    "presignedurl",
    "authorization",
    "cookie",
    "credentials",
    "accesskey",
    "secretkey",
)
SAFE_PASSWORD_METADATA_KEYS = frozenset(
    {
        "mustchangepassword",
        "temporarypasswordexpiresat",
        "passwordchangedat",
        "lastpasswordchangedat",
    }
)


def _normalized_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _is_sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    if normalized in SAFE_PASSWORD_METADATA_KEYS:
        return False
    contains_password_secret = "password" in normalized
    contains_signed_url = "signed" in normalized and normalized.endswith("url")
    return (
        normalized.endswith(SENSITIVE_KEY_SUFFIXES)
        or contains_password_secret
        or contains_signed_url
    )


def redact_snapshot(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else redact_snapshot(nested)
            for key, nested in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_snapshot(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal, Enum)):
        return str(value)
    return str(value)


def record_audit_event(
    *,
    actor: User | None,
    action: AuditAction | str,
    object_type: str,
    object_id: object,
    object_label: str,
    correlation_id: str,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    description: str = "",
    note: str = "",
    actor_display_name: str = "Система",
    actor_role: str = "system",
) -> AuditEvent:
    connection = transaction.get_connection()
    if not connection.in_atomic_block:
        raise RuntimeError("Audit events must be recorded inside transaction.atomic().")

    action_value = str(action)
    section = EVENT_SECTIONS.get(action_value)
    if section is None:
        raise ValueError(f"Unregistered audit action: {action_value}")

    if actor is not None:
        if actor.pk is None:
            raise ValueError("Audit actor must be persisted.")
        actor_display_name = actor.display_name
        actor_role = actor.role

    return AuditEvent.objects.create(
        actor=actor,
        actor_display_name=actor_display_name,
        actor_email=actor.email if actor is not None else "",
        actor_role=actor_role,
        section=section,
        action=action_value,
        object_type=object_type,
        object_id=str(object_id),
        object_label=object_label,
        result="success",
        description=description,
        before=redact_snapshot(before or {}),
        after=redact_snapshot(after or {}),
        note=note,
        correlation_id=correlation_id,
    )
