import csv
from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.analytics import exports as analytics_exports
from apps.audit.models import AuditEvent
from apps.billing.models import (
    CashShift,
    PricingState,
    Receivable,
    ReceivableStatus,
    VisitPricing,
)
from apps.clinic.models import AppointmentStatusConfig, ClinicWorkday, Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.visits.models import Visit, VisitServiceLine, VisitStatus

KYIV = ZoneInfo("Europe/Kyiv")


def moment(day: int, hour: int, minute: int = 0, *, month: int = 7) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=KYIV)


def create_user(*, email: str, role: str, first_name: str) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name=first_name,
        last_name="Коваль",
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def status_config(code: str) -> AppointmentStatusConfig:
    labels = {
        "CONFIRMED": "Підтверджено",
        "COMPLETED": "Завершено",
        "CANCELED": "Скасовано",
        "NO_SHOW": "Неявка",
    }
    status, _ = AppointmentStatusConfig.objects.update_or_create(
        code=code,
        defaults={"label": labels[code], "color": "#39645A"},
    )
    return status


def create_patient(
    *, first_name: str, phone: str, specialist: User, created_at: datetime
) -> Patient:
    patient = Patient.objects.create(
        first_name=first_name,
        last_name="Тестова",
        phone=phone,
        primary_podologist=specialist,
    )
    Patient.objects.filter(pk=patient.pk).update(created_at=created_at)
    patient.refresh_from_db()
    return patient


def create_appointment(
    *,
    patient: Patient,
    specialist: User,
    service: Service,
    room: Room,
    starts_at: datetime,
    status_code: str,
    duration_minutes: int = 60,
) -> Appointment:
    return Appointment.objects.create(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        time_range=(starts_at, starts_at + timedelta(minutes=duration_minutes)),
        duration_minutes=duration_minutes,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=status_config(status_code),
        complaints="",
        has_no_complaints=True,
        cancellation_reason=("Зміна планів" if status_code == "CANCELED" else ""),
    )


def complete_visit(
    *,
    patient: Patient,
    specialist: User,
    service: Service,
    room: Room,
    starts_at: datetime,
    amount_minor: int,
    quantity: int = 1,
) -> Visit:
    with transaction.atomic():
        appointment = create_appointment(
            patient=patient,
            specialist=specialist,
            service=service,
            room=room,
            starts_at=starts_at,
            status_code="COMPLETED",
        )
        visit = Visit.objects.create(
            appointment=appointment,
            patient=patient,
            specialist=specialist,
            status=VisitStatus.DRAFT,
            complaints="",
            has_no_complaints=True,
            started_by=specialist,
        )
        VisitServiceLine.objects.create(
            visit=visit,
            service=service,
            service_code=service.code,
            service_name=service.name,
            duration_minutes=service.duration_minutes,
            price_minor=amount_minor // quantity,
            quantity=quantity,
            is_primary=True,
        )
        VisitPricing.objects.create(
            visit=visit,
            gross_minor=amount_minor,
            discount_amount_minor=0,
            net_minor=amount_minor,
            state=PricingState.OPEN,
        )
        Receivable.objects.create(
            visit=visit,
            amount_minor=amount_minor,
            status=ReceivableStatus.OPEN,
        )
        visit.status = VisitStatus.COMPLETED
        visit.total_minor = amount_minor
        visit.payment_handoff_requested = True
        visit.version = 2
        visit.completed_at = starts_at + timedelta(minutes=60)
        visit.save(
            update_fields=(
                "status",
                "total_minor",
                "payment_handoff_requested",
                "version",
                "completed_at",
                "updated_at",
            )
        )
    return visit


def post_payment(
    *, client: APIClient, visit: Visit, key: str, posted_at: datetime
) -> dict[str, object]:
    with patch("django.utils.timezone.now", return_value=posted_at):
        response = client.post(
            "/api/v1/payments",
            {
                "visit_id": str(visit.pk),
                "payment_method": "CARD",
                "pricing_version": visit.pricing.version,
                "discount_action": "KEEP",
                "comment": "Аналітичний тест",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.mark.django_db
def test_overview_is_role_scoped_and_hides_clinic_finance_from_podologist() -> None:
    podologist = create_user(
        email="overview-podo@example.test", role=UserRole.PODOLOGIST, first_name="Олена"
    )
    other = create_user(
        email="overview-other@example.test", role=UserRole.PODOLOGIST, first_name="Ірина"
    )
    reception = create_user(
        email="overview-reception@example.test", role=UserRole.RECEPTION, first_name="Марина"
    )
    admin = create_user(email="overview-admin@example.test", role=UserRole.ADMIN, first_name="Анна")
    service = Service.objects.create(
        code="OVERVIEW",
        name="Огляд",
        duration_minutes=60,
        price_minor=15_000,
        color="#39645A",
    )
    room_one = Room.objects.create(name="TP804 кабінет 1")
    room_two = Room.objects.create(name="TP804 кабінет 2")
    patient_one = create_patient(
        first_name="Софія",
        phone="0670000001",
        specialist=podologist,
        created_at=moment(1, 9, month=6),
    )
    patient_two = create_patient(
        first_name="Леся",
        phone="0670000002",
        specialist=other,
        created_at=moment(1, 9, month=6),
    )
    own = create_appointment(
        patient=patient_one,
        specialist=podologist,
        service=service,
        room=room_one,
        starts_at=moment(22, 10),
        status_code="CONFIRMED",
    )
    create_appointment(
        patient=patient_two,
        specialist=other,
        service=service,
        room=room_two,
        starts_at=moment(22, 10),
        status_code="CONFIRMED",
    )

    podologist_response = client_for(podologist).get("/api/v1/overview?date=2026-07-22")
    reception_response = client_for(reception).get("/api/v1/overview?date=2026-07-22")
    admin_response = client_for(admin).get("/api/v1/overview?date=2026-07-22")

    assert podologist_response.status_code == 200, podologist_response.json()
    podologist_body = podologist_response.json()
    assert podologist_body["role"] == UserRole.PODOLOGIST
    assert [item["id"] for item in podologist_body["schedule"]] == [str(own.pk)]
    podologist_metric_keys = {item["key"] for item in podologist_body["metrics"]}
    assert podologist_metric_keys == {
        "appointments",
        "patients",
        "workday_minutes",
        "attention",
    }
    assert not {"payments_today_minor", "expected_income_minor"} & podologist_metric_keys

    assert reception_response.status_code == 200, reception_response.json()
    assert len(reception_response.json()["schedule"]) == 2
    assert "payments_today_minor" in {item["key"] for item in reception_response.json()["metrics"]}

    assert admin_response.status_code == 200, admin_response.json()
    assert len(admin_response.json()["schedule"]) == 2
    assert "expected_income_minor" in {item["key"] for item in admin_response.json()["metrics"]}


@pytest.mark.django_db
def test_analytics_is_admin_only_and_validates_the_complete_filter_contract() -> None:
    admin = create_user(
        email="analytics-admin@example.test", role=UserRole.ADMIN, first_name="Анна"
    )
    reception = create_user(
        email="analytics-reception@example.test", role=UserRole.RECEPTION, first_name="Марина"
    )

    allowed = client_for(admin).get("/api/v1/analytics?from=2026-07-01&to=2026-07-31")
    denied = client_for(reception).get("/api/v1/analytics?from=2026-07-01&to=2026-07-31")
    inverted = client_for(admin).get("/api/v1/analytics?from=2026-08-01&to=2026-07-01")
    oversized = client_for(admin).get("/api/v1/analytics?from=2025-01-01&to=2026-07-01")
    missing_specialist = client_for(admin).get(
        "/api/v1/analytics?from=2026-07-01&to=2026-07-31&specialist_id=999999"
    )
    missing_service = client_for(admin).get(
        f"/api/v1/analytics?from=2026-07-01&to=2026-07-31&service_id={uuid4()}"
    )

    assert allowed.status_code == 200, allowed.json()
    assert allowed.json()["period"] == {
        "date_from": "2026-07-01",
        "date_to": "2026-07-31",
        "timezone": "Europe/Kyiv",
        "bucket": "day",
    }
    assert denied.status_code == 403
    assert inverted.status_code == 422
    assert inverted.json()["fields"]["to"]
    assert oversized.status_code == 422
    assert missing_specialist.status_code == 404
    assert missing_service.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_analytics_reconciles_ledger_cohorts_rankings_and_filters() -> None:
    admin = create_user(
        email="reconcile-admin@example.test", role=UserRole.ADMIN, first_name="Анна"
    )
    cashier = create_user(
        email="reconcile-cashier@example.test", role=UserRole.RECEPTION, first_name="Марина"
    )
    specialist = create_user(
        email="reconcile-podo@example.test", role=UserRole.PODOLOGIST, first_name="Олена"
    )
    CashShift.objects.create(employee=cashier)
    service_a = Service.objects.create(
        code="SERVICE-A",
        name="Послуга A",
        duration_minutes=60,
        price_minor=10_000,
        color="#39645A",
    )
    service_b = Service.objects.create(
        code="SERVICE-B",
        name="Послуга B",
        duration_minutes=60,
        price_minor=10_000,
        color="#8A6D3B",
    )
    room = Room.objects.create(name="Аналітичний кабінет")
    for weekday in range(5):
        ClinicWorkday.objects.update_or_create(
            weekday=weekday,
            defaults={
                "is_working": True,
                "start_time": time(9, 0),
                "end_time": time(18, 0),
            },
        )
    returning_patient = create_patient(
        first_name="Повернулась",
        phone="0670000011",
        specialist=specialist,
        created_at=moment(1, 9, month=5),
    )
    new_patient = create_patient(
        first_name="Нова",
        phone="0670000012",
        specialist=specialist,
        created_at=moment(2, 9),
    )
    complete_visit(
        patient=returning_patient,
        specialist=specialist,
        service=service_a,
        room=room,
        starts_at=moment(20, 9, month=6),
        amount_minor=10_000,
    )
    returning_visit = complete_visit(
        patient=returning_patient,
        specialist=specialist,
        service=service_a,
        room=room,
        starts_at=moment(5, 9),
        amount_minor=10_000,
    )
    new_visit = complete_visit(
        patient=new_patient,
        specialist=specialist,
        service=service_b,
        room=room,
        starts_at=moment(10, 9),
        amount_minor=20_000,
        quantity=2,
    )
    create_appointment(
        patient=returning_patient,
        specialist=specialist,
        service=service_a,
        room=room,
        starts_at=moment(15, 9),
        status_code="CANCELED",
    )
    create_appointment(
        patient=new_patient,
        specialist=specialist,
        service=service_b,
        room=room,
        starts_at=moment(16, 9),
        status_code="NO_SHOW",
    )

    cashier_client = client_for(cashier)
    first_payment = post_payment(
        client=cashier_client,
        visit=returning_visit,
        key="analytics-payment-a",
        posted_at=moment(6, 12),
    )
    post_payment(
        client=cashier_client,
        visit=new_visit,
        key="analytics-payment-b",
        posted_at=moment(11, 12),
    )
    payment_id = first_payment["operation"]["payment"]["id"]
    with patch("django.utils.timezone.now", return_value=moment(12, 12)):
        refunded = cashier_client.post(
            f"/api/v1/payments/{payment_id}/refunds",
            {"reason": "Звірення аналітики"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="analytics-refund-a",
        )
    assert refunded.status_code == 201, refunded.json()

    response = client_for(admin).get("/api/v1/analytics?from=2026-07-01&to=2026-07-31")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["kpis"] == {
        "completed_visits": 2,
        "revenue_minor": 20_000,
        "payment_count": 2,
        "average_check_minor": 10_000,
        "returning_patient_rate_bps": 5_000,
        "returning_patients": 1,
        "served_patients": 2,
        "new_patients": 1,
        "canceled_appointments": 1,
        "no_show_appointments": 1,
        "average_return_interval_days": 15,
    }
    assert sum(point["revenue_minor"] for point in body["trend"]) == 20_000
    assert {item["code"]: item["count"] for item in body["appointment_outcomes"]} == {
        "COMPLETED": 2,
        "CANCELED": 1,
        "NO_SHOW": 1,
        "OTHER": 0,
    }
    assert [
        (item["code"], item["quantity"], item["billed_total_minor"])
        for item in body["service_ranking"]
    ] == [
        ("SERVICE-B", 2, 20_000),
        ("SERVICE-A", 1, 10_000),
    ]
    performance = body["specialist_performance"][0]
    assert performance["id"] == specialist.pk
    assert performance["completed_visits"] == 2
    assert performance["scheduled_minutes"] == 180
    assert performance["revenue_minor"] == 20_000
    assert performance["utilization_bps"] == min(
        10_000,
        round(performance["scheduled_minutes"] * 10_000 / performance["available_minutes"]),
    )

    filtered = client_for(admin).get(
        f"/api/v1/analytics?from=2026-07-01&to=2026-07-31&service_id={service_b.pk}"
    )
    assert filtered.status_code == 200, filtered.json()
    filtered_body = filtered.json()
    assert filtered_body["kpis"]["completed_visits"] == 1
    assert filtered_body["kpis"]["revenue_minor"] == 20_000
    assert filtered_body["kpis"]["payment_count"] == 1
    assert [item["id"] for item in filtered_body["service_ranking"]] == [str(service_b.pk)]
    assert UUID(filtered_body["filters"]["service"]["id"]) == service_b.pk


@pytest.mark.django_db(transaction=True)
def test_analytics_export_is_filtered_summary_first_safe_and_contains_no_raw_identifiers() -> None:
    admin = create_user(
        email="analytics-export-admin@example.test", role=UserRole.ADMIN, first_name="Анна"
    )
    cashier = create_user(
        email="analytics-export-cashier@example.test",
        role=UserRole.RECEPTION,
        first_name="Марина",
    )
    specialist = create_user(
        email="analytics-export-podo@example.test",
        role=UserRole.PODOLOGIST,
        first_name="=Олена",
    )
    CashShift.objects.create(employee=cashier)
    service = Service.objects.create(
        code="@SERVICE-EXPORT",
        name="+Послуга export",
        duration_minutes=60,
        price_minor=15_000,
        color="#39645A",
    )
    room = Room.objects.create(name="Export кабінет")
    ClinicWorkday.objects.update_or_create(
        weekday=0,
        defaults={"is_working": True, "start_time": time(9, 0), "end_time": time(18, 0)},
    )
    patient = create_patient(
        first_name="PRIVATE-PATIENT-MARKER",
        phone="0679999988",
        specialist=specialist,
        created_at=moment(2, 9),
    )
    visit = complete_visit(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        starts_at=moment(5, 9),
        amount_minor=15_000,
    )
    post_payment(
        client=client_for(cashier),
        visit=visit,
        key="analytics-export-payment",
        posted_at=moment(6, 12),
    )
    audit_count = AuditEvent.objects.count()

    response = client_for(admin).get(
        "/api/v1/analytics/export",
        {
            "from": "2026-07-01",
            "to": "2026-07-31",
            "specialist_id": specialist.pk,
            "service_id": str(service.pk),
        },
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Cache-Control"] == "no-store"
    assert response["Content-Disposition"].startswith('attachment; filename="analytics-report-')
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content
    decoded = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(decoded, newline=""))
    rows = list(reader)
    assert reader.fieldnames == list(analytics_exports.ANALYTICS_EXPORT_COLUMNS)
    assert len(reader.fieldnames) == 34
    assert response["X-Export-Row-Count"] == str(len(rows))
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert rows[0]["completed_visits"] == "1"
    assert rows[0]["revenue_minor"] == "15000"
    assert rows[0]["payment_count"] == "1"
    assert rows[0]["filter_specialist_name"] == "'=Олена Коваль"
    assert rows[0]["filter_service_name"] == "'+Послуга export"
    assert [row["row_type"] for row in rows] == sorted(
        [row["row_type"] for row in rows],
        key=(
            "REPORT_SUMMARY",
            "TREND",
            "APPOINTMENT_OUTCOME",
            "SPECIALIST_PERFORMANCE",
            "SERVICE_RANKING",
        ).index,
    )
    specialist_row = next(row for row in rows if row["row_type"] == "SPECIALIST_PERFORMANCE")
    service_row = next(row for row in rows if row["row_type"] == "SERVICE_RANKING")
    assert specialist_row["dimension_name"] == "'=Олена Коваль"
    assert service_row["dimension_code"] == "'@SERVICE-EXPORT"
    assert service_row["dimension_name"] == "'+Послуга export"
    assert "PRIVATE-PATIENT-MARKER" not in decoded
    assert "0679999988" not in decoded
    assert str(patient.pk) not in decoded
    assert str(visit.pk) not in decoded
    assert AuditEvent.objects.count() == audit_count


@pytest.mark.django_db
def test_analytics_export_empty_report_keeps_summary_trend_and_canonical_outcomes() -> None:
    admin = create_user(
        email="analytics-export-empty@example.test", role=UserRole.ADMIN, first_name="Анна"
    )

    response = client_for(admin).get("/api/v1/analytics/export?from=2026-07-01&to=2026-07-02")

    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert rows[0]["completed_visits"] == "0"
    assert rows[0]["average_return_interval_days"] == ""
    assert [row["row_type"] for row in rows].count("TREND") == 2
    outcomes = [row["dimension_code"] for row in rows if row["row_type"] == "APPOINTMENT_OUTCOME"]
    assert outcomes == ["COMPLETED", "CANCELED", "NO_SHOW", "OTHER"]
    assert not any(row["row_type"] == "SPECIALIST_PERFORMANCE" for row in rows)
    assert not any(row["row_type"] == "SERVICE_RANKING" for row in rows)


@pytest.mark.django_db
def test_analytics_export_repeats_admin_scope_and_filter_validation() -> None:
    admin = create_user(
        email="analytics-export-scope-admin@example.test",
        role=UserRole.ADMIN,
        first_name="Анна",
    )
    reception = create_user(
        email="analytics-export-scope-reception@example.test",
        role=UserRole.RECEPTION,
        first_name="Марина",
    )
    podologist = create_user(
        email="analytics-export-scope-podo@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
    )
    query = "?from=2026-07-01&to=2026-07-31"

    allowed = client_for(admin).get(f"/api/v1/analytics/export{query}")
    reception_denied = client_for(reception).get(f"/api/v1/analytics/export{query}")
    podologist_denied = client_for(podologist).get(f"/api/v1/analytics/export{query}")
    anonymous_denied = APIClient().get(f"/api/v1/analytics/export{query}")
    inverted = client_for(admin).get("/api/v1/analytics/export?from=2026-08-01&to=2026-07-01")
    oversized = client_for(admin).get("/api/v1/analytics/export?from=2025-01-01&to=2026-07-01")
    missing_specialist = client_for(admin).get(
        f"/api/v1/analytics/export{query}&specialist_id=999999"
    )
    missing_service = client_for(admin).get(f"/api/v1/analytics/export{query}&service_id={uuid4()}")

    assert allowed.status_code == 200
    assert reception_denied.status_code == 403
    assert podologist_denied.status_code == 403
    assert anonymous_denied.status_code == 401
    assert inverted.status_code == 422
    assert oversized.status_code == 422
    assert missing_specialist.status_code == 404
    assert missing_service.status_code == 404


@pytest.mark.django_db
def test_analytics_export_limit_returns_json_without_partial_csv() -> None:
    admin = create_user(
        email="analytics-export-limit@example.test", role=UserRole.ADMIN, first_name="Анна"
    )
    with (
        patch.object(
            analytics_exports,
            "analytics_export_row_count",
            return_value=analytics_exports.ANALYTICS_EXPORT_ROW_LIMIT + 1,
        ),
        patch.object(analytics_exports, "render_analytics_csv") as render_csv,
    ):
        response = client_for(admin).get("/api/v1/analytics/export?from=2026-07-01&to=2026-07-31")

    assert response.status_code == 422
    assert response.json()["code"] == "analytics_export_too_large"
    assert response["Content-Type"].startswith("application/json")
    render_csv.assert_not_called()


def test_analytics_csv_sanitizes_nul_before_formula_detection() -> None:
    result = {
        "period": {
            "from": datetime(2026, 7, 1).date(),
            "to": datetime(2026, 7, 1).date(),
            "timezone": "Europe/Kyiv",
            "bucket": "day",
        },
        "filters": {
            "specialist": {"id": "1", "name": "\x00=Фільтр", "is_active": True},
            "service": None,
        },
        "kpis": {
            "completed_visits": 0,
            "revenue_minor": 0,
            "payment_count": 0,
            "average_check_minor": 0,
            "returning_patient_rate_bps": 0,
            "returning_patients": 0,
            "served_patients": 0,
            "new_patients": 0,
            "canceled_appointments": 0,
            "no_show_appointments": 0,
            "average_return_interval_days": None,
        },
        "trend": [
            {
                "from": datetime(2026, 7, 1).date(),
                "to": datetime(2026, 7, 1).date(),
                "label": "\x00+День",
                "visits": 0,
                "revenue_minor": 0,
            }
        ],
        "appointment_outcomes": [],
        "specialist_performance": [],
        "service_ranking": [],
    }

    decoded = analytics_exports.render_analytics_csv(result).decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(decoded, newline="")))

    assert "\x00" not in decoded
    assert rows[0]["filter_specialist_name"] == "'=Фільтр"
    assert rows[1]["dimension_name"] == "'+День"
