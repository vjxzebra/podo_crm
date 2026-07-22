from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent, AuditEventImmutableError
from apps.audit.registry import EVENT_SECTIONS, AuditAction, AuditSection
from apps.audit.services import REDACTED, record_audit_event


def create_admin() -> User:
    return User.objects.create_user(
        email="admin@example.test",
        role=UserRole.ADMIN,
        first_name="Ірина",
        last_name="Коваль",
    )


@pytest.mark.django_db(transaction=True)
def test_service_requires_atomic_domain_transaction():
    actor = create_admin()

    with pytest.raises(RuntimeError, match="transaction.atomic"):
        record_audit_event(
            actor=actor,
            action=AuditAction.SETTINGS_UPDATED,
            object_type="clinic_profile",
            object_id="primary",
            object_label="Podoria",
            correlation_id="request-outside-transaction",
        )

    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_service_redacts_nested_secrets_and_normalizes_json_values():
    actor = create_admin()
    occurred_at = datetime(2026, 7, 21, 10, 30, tzinfo=UTC)
    reference = uuid4()

    with transaction.atomic():
        event = record_audit_event(
            actor=actor,
            action=AuditAction.SETTINGS_UPDATED,
            object_type="clinic_profile",
            object_id=reference,
            object_label="Podoria",
            correlation_id="redaction-check",
            before={"phone": "+380000000000"},
            after={
                "new_password": "never-store-this",
                "temporary_password_expires_at": occurred_at,
                "private": [
                    {"session_key": "session-secret"},
                    {"signed_photo_url": "https://private.example/photo"},
                ],
                "price": Decimal("125.50"),
                "reference": reference,
            },
        )

    assert event.after == {
        "new_password": REDACTED,
        "temporary_password_expires_at": occurred_at.isoformat(),
        "private": [
            {"session_key": REDACTED},
            {"signed_photo_url": REDACTED},
        ],
        "price": "125.50",
        "reference": str(reference),
    }
    assert event.actor_display_name == "Ірина Коваль"
    assert event.actor_role == UserRole.ADMIN


@pytest.mark.django_db
def test_rolled_back_domain_mutation_leaves_no_audit_event():
    actor = create_admin()

    with pytest.raises(RuntimeError, match="domain failure"), transaction.atomic():
        record_audit_event(
            actor=actor,
            action=AuditAction.SETTINGS_UPDATED,
            object_type="clinic_profile",
            object_id="primary",
            object_label="Podoria",
            correlation_id="rollback-check",
        )
        raise RuntimeError("domain failure")

    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_model_queryset_and_database_reject_event_mutation():
    actor = create_admin()
    with transaction.atomic():
        event = record_audit_event(
            actor=actor,
            action=AuditAction.SETTINGS_UPDATED,
            object_type="clinic_profile",
            object_id="primary",
            object_label="Podoria",
            correlation_id="immutability-check",
            description="Original",
        )

    event.description = "Changed"
    with pytest.raises(AuditEventImmutableError):
        event.save()
    with pytest.raises(AuditEventImmutableError):
        AuditEvent.objects.filter(pk=event.pk).update(description="Changed")
    with pytest.raises(AuditEventImmutableError):
        event.delete()

    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_auditevent SET description = %s WHERE id = %s",
                ["Changed through SQL", event.pk],
            )

    event.refresh_from_db()
    assert event.description == "Original"


@pytest.mark.django_db
def test_unregistered_action_is_rejected_without_side_effect():
    actor = create_admin()

    with pytest.raises(ValueError, match="Unregistered"), transaction.atomic():
        record_audit_event(
            actor=actor,
            action="settings.unregistered_action",
            object_type="clinic_profile",
            object_id="primary",
            object_label="Podoria",
            correlation_id="registry-check",
        )

    assert not AuditEvent.objects.exists()


def test_registry_covers_every_action_and_required_spec_families():
    registered_actions = set(EVENT_SECTIONS)
    declared_actions = {action.value for action in AuditAction}

    assert registered_actions == declared_actions
    assert set(EVENT_SECTIONS.values()) == set(AuditSection)
    assert {
        AuditAction.APPOINTMENT_CREATED,
        AuditAction.APPOINTMENT_UPDATED,
        AuditAction.APPOINTMENT_RESCHEDULED,
        AuditAction.APPOINTMENT_CANCELED,
        AuditAction.PATIENT_CREATED,
        AuditAction.PATIENT_UPDATED,
        AuditAction.MEDICAL_RECORD_UPDATED,
        AuditAction.VISIT_COMPLETED,
        AuditAction.PAYMENT_POSTED,
        AuditAction.REFUND_POSTED,
        AuditAction.CASH_DEPOSIT_POSTED,
        AuditAction.CASH_WITHDRAWAL_POSTED,
        AuditAction.CASH_SHIFT_OPENED,
        AuditAction.CASH_SHIFT_CLOSED,
        AuditAction.STOCK_MOVEMENT_POSTED,
        AuditAction.STOCKTAKE_POSTED,
        AuditAction.USER_CREATED,
        AuditAction.USER_ROLE_CHANGED,
        AuditAction.USER_DEACTIVATED,
        AuditAction.PASSWORD_CHANGED,
        AuditAction.PASSWORD_RESET_REQUESTED,
        AuditAction.CLINIC_PROFILE_UPDATED,
    } <= registered_actions
