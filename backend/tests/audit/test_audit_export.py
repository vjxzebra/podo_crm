import csv
from datetime import datetime, timedelta
from io import StringIO

import pytest
from django.db import transaction
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.audit import exports as audit_exports
from apps.audit.exports import AUDIT_EXPORT_COLUMNS, render_audit_csv
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction, AuditSection
from apps.audit.services import record_audit_event


def create_user(role: str, email: str, *, first_name: str = "Олена") -> User:
    return User.objects.create_user(
        email=email,
        role=role,
        first_name=first_name,
        last_name="Мельник",
    )


def create_event(
    actor: User,
    *,
    action: AuditAction = AuditAction.USER_ROLE_CHANGED,
    object_id: str = "internal-object-marker",
    object_label: str = "Працівник без internal ID",
    description: str = "Змінено роль працівника.",
) -> AuditEvent:
    with transaction.atomic():
        return record_audit_event(
            actor=actor,
            action=action,
            object_type="user",
            object_id=object_id,
            object_label=object_label,
            correlation_id="correlation-private-marker",
            before={"clinical_notes": "before-private-marker"},
            after={"clinical_notes": "after-private-marker"},
            description=description,
            note="note-private-marker",
        )


def parsed_rows(response) -> tuple[list[str], list[dict[str, str]]]:
    text = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text, newline=""))
    return list(reader.fieldnames or []), list(reader)


@pytest.mark.django_db
def test_export_is_summary_first_ordered_minimal_and_read_only():
    admin = create_user(UserRole.ADMIN, "audit-admin-private@example.test")
    older = create_event(admin)
    newer = create_event(
        admin,
        action=AuditAction.SETTINGS_UPDATED,
        object_id="second-internal-marker",
        object_label="Podoria",
        description="Оновлено налаштування.",
    )
    count_before = AuditEvent.objects.count()
    client = Client()
    client.force_login(admin)

    list_response = client.get("/api/v1/audit-events")
    response = client.get("/api/v1/audit-events/export")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"].startswith('attachment; filename="audit-events-')
    assert response["Cache-Control"] == "no-store"
    assert response["X-Export-Event-Count"] == "2"
    assert response["X-Export-Row-Count"] == "3"
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content

    columns, rows = parsed_rows(response)
    assert columns == list(AUDIT_EXPORT_COLUMNS)
    assert len(columns) == 28
    assert [row["row_type"] for row in rows] == [
        "REPORT_SUMMARY",
        "AUDIT_EVENT",
        "AUDIT_EVENT",
    ]
    assert rows[0]["event_count"] == "2"
    assert rows[0]["team_count"] == "1"
    assert rows[0]["settings_count"] == "1"
    assert rows[0]["inventory_count"] == "0"
    assert (
        [row["event_id"] for row in rows[1:]]
        == [item["id"] for item in list_response.json()["events"]]
        == [str(newer.pk), str(older.pk)]
    )
    assert rows[1]["occurred_at_local"] == timezone.localtime(newer.occurred_at).isoformat(
        timespec="seconds"
    )

    forbidden_columns = {
        "actor_email",
        "actor_id",
        "object_id",
        "before",
        "after",
        "changes",
        "note",
        "correlation_id",
    }
    assert forbidden_columns.isdisjoint(columns)
    decoded = response.content.decode("utf-8-sig")
    for marker in (
        "audit-admin-private@example.test",
        "internal-object-marker",
        "second-internal-marker",
        "before-private-marker",
        "after-private-marker",
        "note-private-marker",
        "correlation-private-marker",
    ):
        assert marker not in decoded
    assert AuditEvent.objects.count() == count_before


@pytest.mark.django_db
def test_export_uses_exact_five_applied_list_filters():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    included = create_event(admin)
    other = create_user(UserRole.RECEPTION, "other@example.test")
    create_event(
        other,
        action=AuditAction.SETTINGS_UPDATED,
        object_label="Інша подія",
        description="Оновлено налаштування.",
    )
    date_from = included.occurred_at - timedelta(seconds=1)
    date_to = included.occurred_at + timedelta(seconds=1)
    query = {
        "search": "роль",
        "actor_id": admin.pk,
        "section": AuditSection.TEAM,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }
    client = Client()
    client.force_login(admin)

    listing = client.get("/api/v1/audit-events", query)
    response = client.get("/api/v1/audit-events/export", query)

    assert listing.status_code == 200
    assert response.status_code == 200
    _, rows = parsed_rows(response)
    assert [item["id"] for item in listing.json()["events"]] == [str(included.pk)]
    assert [row["event_id"] for row in rows[1:]] == [str(included.pk)]
    summary = rows[0]
    assert summary["filter_search"] == "роль"
    assert summary["filter_actor_id"] == str(admin.pk)
    assert summary["filter_section"] == AuditSection.TEAM
    assert (
        abs((datetime.fromisoformat(summary["filter_date_from"]) - date_from).total_seconds()) < 1
    )
    assert abs((datetime.fromisoformat(summary["filter_date_to"]) - date_to).total_seconds()) < 1


@pytest.mark.django_db
def test_empty_export_still_contains_one_summary_row():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    client = Client()
    client.force_login(admin)

    response = client.get("/api/v1/audit-events/export", {"search": "missing"})

    assert response.status_code == 200
    columns, rows = parsed_rows(response)
    assert columns == list(AUDIT_EXPORT_COLUMNS)
    assert len(rows) == 1
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert rows[0]["event_count"] == "0"
    assert all(rows[0][f"{section.value}_count"] == "0" for section in AuditSection)
    assert response["X-Export-Event-Count"] == "0"
    assert response["X-Export-Row-Count"] == "1"


@pytest.mark.django_db
def test_export_enforces_rbac_range_and_supported_query():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    create_event(admin)

    assert Client().get("/api/v1/audit-events/export").status_code == 401
    for role in (UserRole.RECEPTION, UserRole.PODOLOGIST):
        client = Client()
        client.force_login(create_user(role, f"{role}@example.test"))
        assert client.get("/api/v1/audit-events/export").status_code == 403

    client = Client()
    client.force_login(admin)
    now = timezone.now()
    inverted = client.get(
        "/api/v1/audit-events/export",
        {"date_from": now.isoformat(), "date_to": (now - timedelta(seconds=1)).isoformat()},
    )
    oversized = client.get(
        "/api/v1/audit-events/export",
        {
            "date_from": (now - timedelta(days=367)).isoformat(),
            "date_to": now.isoformat(),
        },
    )
    unsupported = client.get(
        "/api/v1/audit-events/export",
        {"cursor": "00000000-0000-4000-8000-000000000001", "unexpected": "value"},
    )

    assert inverted.status_code == 422
    assert "date_to" in inverted.json()["fields"]
    assert oversized.status_code == 422
    assert "date_to" in oversized.json()["fields"]
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == "audit_export_query_not_supported"
    assert set(unsupported.json()["fields"]) == {"cursor", "unexpected"}


@pytest.mark.django_db
def test_export_limit_returns_json_error_without_partial_csv(monkeypatch):
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    create_event(admin)
    create_event(admin, action=AuditAction.SETTINGS_UPDATED)
    monkeypatch.setattr(audit_exports, "AUDIT_EXPORT_ROW_LIMIT", 1)
    client = Client()
    client.force_login(admin)

    response = client.get("/api/v1/audit-events/export")

    assert response.status_code == 422
    assert response.json()["code"] == "audit_export_too_large"
    assert response["Content-Type"].startswith("application/json")
    assert "Content-Disposition" not in response


@pytest.mark.django_db
def test_renderer_removes_nul_before_formula_detection():
    admin = create_user(UserRole.ADMIN, "admin@example.test", first_name="=Actor")
    event = create_event(
        admin,
        object_label="@Object",
        description="+Description",
    )
    event.actor_display_name = "\x00=Actor"
    event.object_label = "\x00@Object"
    event.description = "\x00+Description"

    reader = csv.DictReader(
        StringIO(
            render_audit_csv([event], {}).decode("utf-8-sig"),
            newline="",
        )
    )
    rows = list(reader)

    assert rows[1]["actor_name"] == "'=Actor"
    assert rows[1]["object_label"] == "'@Object"
    assert rows[1]["description"] == "'+Description"
    assert "\x00" not in str(rows)
