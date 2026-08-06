from datetime import timedelta
from typing import Never
from uuid import uuid4

import pytest
from django.db import connection
from django.db.models import F
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.billing.models import Payment, PaymentMethod, Receivable, VisitPricing
from apps.billing.selectors import payment_receivables_for_global_search
from apps.billing.services import open_cash_shift, post_payment
from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.global_search import selectors as global_search_selectors
from apps.inventory.models import Material, MaterialLot
from apps.inventory.selectors import materials_for_global_search
from apps.patients.models import Patient
from apps.patients.selectors import patients_for_global_search
from apps.scheduling.models import Appointment
from apps.scheduling.selectors import appointments_for_global_search
from apps.visits.models import Visit, VisitServiceLine, VisitStatus
from tests.financial_fixtures import complete_visit_with_neutral_pricing

PASSWORD = "test-only-password-placeholder"  # noqa: S105


def create_user(*, email: str, role: str, first_name: str) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name=first_name,
        last_name="Тестовий",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def post_fixture_payment(
    *,
    actor: User,
    receivable: Receivable,
    correlation_id: str,
    idempotency_key: str,
) -> None:
    pricing = VisitPricing.objects.get(visit_id=receivable.visit_id)
    post_payment(
        actor=actor,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        data={
            "visit_id": receivable.visit_id,
            "payment_method": PaymentMethod.CARD,
            "comment": "",
            "pricing_version": pricing.version,
            "discount_action": "KEEP",
        },
    )


def domain_fixture() -> dict[str, object]:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN, first_name="Адмін")
    reception = create_user(
        email="reception@example.test",
        role=UserRole.RECEPTION,
        first_name="Ресепшн",
    )
    owner = create_user(
        email="owner@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
    )
    foreign = create_user(
        email="foreign@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Ірина",
    )
    patient = Patient.objects.create(
        first_name="Марія",
        last_name="Орбіта",
        phone="+380 67 123 45 67",
        primary_podologist=owner,
    )
    service = Service.objects.create(
        code="ORBIT-CARE",
        name="Орбіта терапія",
        duration_minutes=45,
        price_minor=125_000,
        color="#0F766E",
    )
    room = Room.objects.create(name="Орбіта кабінет")
    completed = AppointmentStatusConfig.objects.get(code="COMPLETED")
    starts_at = timezone.now() - timedelta(hours=2)
    appointment = Appointment.objects.create(
        patient=patient,
        specialist=owner,
        service=service,
        room=room,
        time_range=(starts_at, starts_at + timedelta(minutes=45)),
        duration_minutes=45,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=completed,
        complaints="",
        has_no_complaints=True,
    )
    visit = Visit.objects.create(
        appointment=appointment,
        patient=patient,
        specialist=owner,
        status=VisitStatus.DRAFT,
        complaints="",
        has_no_complaints=True,
        total_minor=None,
        payment_handoff_requested=False,
        version=2,
        started_by=owner,
        completed_at=None,
    )
    VisitServiceLine.objects.create(
        visit=visit,
        service=service,
        service_code=service.code,
        service_name=service.name,
        duration_minutes=service.duration_minutes,
        price_minor=service.price_minor,
        quantity=1,
        is_primary=True,
    )
    _, receivable = complete_visit_with_neutral_pricing(
        visit,
        completed_at=starts_at + timedelta(minutes=45),
        payment_handoff_requested=True,
    )
    material = Material.objects.create(
        sku="ORBIT-001",
        name="Орбіта гель",
        category="Догляд",
        unit="мл",
        minimum_quantity=10,
    )
    return {
        "admin": admin,
        "reception": reception,
        "owner": owner,
        "foreign": foreign,
        "patient": patient,
        "appointment": appointment,
        "receivable": receivable,
        "material": material,
    }


@pytest.mark.django_db
def test_search_requires_authentication_and_valid_normalized_query() -> None:
    assert APIClient().get("/api/v1/search", {"q": "орбіта"}).status_code == 401
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN, first_name="Адмін")
    client = authenticated_client(admin)

    missing = client.get("/api/v1/search")
    short = client.get("/api/v1/search", {"q": "  а  "})
    long = client.get("/api/v1/search", {"q": "а" * 101})
    empty_types = client.get("/api/v1/search", {"q": "тест", "types": " "})
    unknown_types = client.get("/api/v1/search", {"q": "тест", "types": "patients,secrets"})

    assert [missing.status_code, short.status_code, long.status_code] == [422, 422, 422]
    assert empty_types.status_code == unknown_types.status_code == 422
    assert "q" in missing.json()["fields"]
    assert "types" in unknown_types.json()["fields"]


@pytest.mark.django_db
def test_admin_searches_all_groups_in_canonical_order_with_safe_common_items() -> None:
    fixture = domain_fixture()
    response = authenticated_client(fixture["admin"]).get(  # type: ignore[arg-type]
        "/api/v1/search",
        {"q": "  ОРБІТА  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "орбіта"
    assert [group["type"] for group in body["groups"]] == [
        "patients",
        "appointments",
        "payments",
        "materials",
    ]
    assert body["returned_count"] == 4
    items = [group["items"][0] for group in body["groups"]]
    assert [item["type"] for item in items] == [
        "patient",
        "appointment",
        "payment",
        "material",
    ]
    assert all(
        set(item) == {"type", "id", "title", "subtitle", "meta", "deep_link"} for item in items
    )
    assert items[0]["deep_link"] == f"/patients/{fixture['patient'].pk}/overview"  # type: ignore[union-attr]
    assert items[1]["deep_link"] == f"/calendar?appointment={fixture['appointment'].pk}"  # type: ignore[union-attr]
    assert items[2]["deep_link"] == f"/finance?operation=PAYMENT:{fixture['receivable'].pk}"  # type: ignore[union-attr]
    assert items[3]["deep_link"] == f"/inventory?material={fixture['material'].pk}"  # type: ignore[union-attr]
    assert "available" not in items[0]
    assert "note" not in items[0]


@pytest.mark.django_db
def test_roles_omit_forbidden_categories_and_foreign_objects_without_querying_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = domain_fixture()
    reception = authenticated_client(fixture["reception"])  # type: ignore[arg-type]
    owner = authenticated_client(fixture["owner"])  # type: ignore[arg-type]
    foreign = authenticated_client(fixture["foreign"])  # type: ignore[arg-type]

    reception_body = reception.get("/api/v1/search", {"q": "орбіта"}).json()
    owner_body = owner.get("/api/v1/search", {"q": "орбіта"}).json()
    foreign_body = foreign.get("/api/v1/search", {"q": "орбіта"}).json()

    assert [group["type"] for group in reception_body["groups"]] == [
        "patients",
        "appointments",
        "payments",
    ]
    assert [group["type"] for group in owner_body["groups"]] == [
        "patients",
        "appointments",
    ]
    assert foreign_body == {"query": "орбіта", "groups": [], "returned_count": 0}

    def forbidden_selector(_actor: User, _search: str) -> Never:
        raise AssertionError("A forbidden search selector must not be invoked.")

    material_item_factory = global_search_selectors._CATEGORY_HANDLERS["materials"][1]
    monkeypatch.setitem(
        global_search_selectors._CATEGORY_HANDLERS,
        "materials",
        (forbidden_selector, material_item_factory),
    )
    with CaptureQueriesContext(connection) as captured:
        hidden = reception.get(
            "/api/v1/search",
            {"q": "ORBIT-001", "types": "materials"},
        )
    assert hidden.json() == {"query": "orbit-001", "groups": [], "returned_count": 0}
    sql = " ".join(query["sql"].lower() for query in captured.captured_queries)
    assert "inventory_material" not in sql

    payment_item_factory = global_search_selectors._CATEGORY_HANDLERS["payments"][1]
    monkeypatch.setitem(
        global_search_selectors._CATEGORY_HANDLERS,
        "payments",
        (forbidden_selector, payment_item_factory),
    )
    with CaptureQueriesContext(connection) as captured:
        hidden = owner.get(
            "/api/v1/search",
            {"q": str(fixture["receivable"].pk), "types": "payments,materials"},  # type: ignore[union-attr]
        )
    assert hidden.json()["groups"] == []
    sql = " ".join(query["sql"].lower() for query in captured.captured_queries)
    assert "billing_receivable" not in sql
    assert "inventory_material" not in sql


@pytest.mark.django_db
def test_types_are_deduplicated_and_results_keep_canonical_group_order() -> None:
    fixture = domain_fixture()
    response = authenticated_client(fixture["admin"]).get(  # type: ignore[arg-type]
        "/api/v1/search",
        {"q": "орбіта", "types": "materials,patients,materials"},
    )
    assert response.status_code == 200
    assert [group["type"] for group in response.json()["groups"]] == [
        "patients",
        "materials",
    ]


@pytest.mark.django_db
def test_nfkc_casefold_normalization_and_exact_identifier_ranking() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN, first_name="Адмін")
    exact = Patient.objects.create(
        public_number="P-RANK-EXACT",
        first_name="Maria",
        last_name="Exact",
        phone="0671111111",
    )
    Patient.objects.create(
        first_name="P-RANK-EXACT similar",
        last_name="Result",
        phone="0672222222",
    )
    client = authenticated_client(admin)

    normalized = client.get("/api/v1/search", {"q": "  ＭＡＲＩＡ  ", "types": "patients"})
    ranked = client.get(
        "/api/v1/search",
        {"q": "p-rank-exact", "types": "patients"},
    )

    assert normalized.status_code == ranked.status_code == 200
    assert normalized.json()["query"] == "maria"
    assert normalized.json()["groups"][0]["items"][0]["id"] == str(exact.pk)
    assert ranked.json()["groups"][0]["items"][0]["id"] == str(exact.pk)


@pytest.mark.django_db
def test_search_ranking_uses_frozen_identifier_name_substring_tiers() -> None:
    admin = create_user(
        email="rank-admin@example.test",
        role=UserRole.ADMIN,
        first_name="Адмін",
    )
    specialist = create_user(
        email="rank-specialist@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Фахівець",
    )
    service = Service.objects.create(
        code="NEUTRAL-SERVICE",
        name="Нейтральна послуга",
        duration_minutes=30,
        price_minor=10_000,
        color="#0F766E",
    )
    room = Room.objects.create(name="Ranking room")
    completed = AppointmentStatusConfig.objects.get(code="COMPLETED")
    starts_at = timezone.now() - timedelta(days=2)
    patient_specs = (
        ("exact", "RANK", "Neutral", "Exact"),
        ("identifier_prefix", "RANK-PREFIX", "Neutral", "Prefix"),
        ("name_prefix", "", "Rank", "Name"),
        ("substring", "", "X rank", "Substring"),
    )
    patients: dict[str, Patient] = {}
    appointments: dict[str, Appointment] = {}
    receivables: dict[str, Receivable] = {}
    for index, (tier, public_number, first_name, last_name) in enumerate(patient_specs):
        patient = Patient.objects.create(
            public_number=public_number,
            first_name=first_name,
            last_name=last_name,
            phone=f"06790000{index:02d}",
        )
        appointment_start = starts_at + timedelta(hours=index)
        appointment = Appointment.objects.create(
            public_number=public_number,
            patient=patient,
            specialist=specialist,
            service=service,
            room=room,
            time_range=(appointment_start, appointment_start + timedelta(minutes=30)),
            duration_minutes=30,
            service_name_snapshot=service.name,
            service_color_snapshot=service.color,
            room_label_snapshot=room.name,
            status=completed,
            complaints="",
            has_no_complaints=True,
        )
        visit = Visit.objects.create(
            public_number=public_number,
            appointment=appointment,
            patient=patient,
            specialist=specialist,
            status=VisitStatus.DRAFT,
            complaints="",
            has_no_complaints=True,
            total_minor=None,
            payment_handoff_requested=False,
            version=2,
            started_by=specialist,
            completed_at=None,
        )
        VisitServiceLine.objects.create(
            visit=visit,
            service=service,
            service_code=service.code,
            service_name=service.name,
            duration_minutes=service.duration_minutes,
            price_minor=service.price_minor,
            quantity=1,
            is_primary=True,
        )
        _, receivable = complete_visit_with_neutral_pricing(
            visit,
            completed_at=appointment_start + timedelta(minutes=30),
            payment_handoff_requested=True,
        )
        patients[tier] = patient
        appointments[tier] = appointment
        receivables[tier] = receivable

    materials = {
        "exact": Material.objects.create(
            sku="RANK",
            name="Neutral exact",
            category="Test",
            unit="шт",
        ),
        "identifier_prefix": Material.objects.create(
            sku="RANK-PREFIX",
            name="Neutral prefix",
            category="Test",
            unit="шт",
        ),
        "name_prefix": Material.objects.create(
            sku="NEUTRAL-NAME",
            name="Rank material",
            category="Test",
            unit="шт",
        ),
        "substring": Material.objects.create(
            sku="NEUTRAL-SUBSTRING",
            name="X rank material",
            category="Test",
            unit="шт",
        ),
    }
    expected_tiers = ["exact", "identifier_prefix", "name_prefix", "substring"]

    assert list(patients_for_global_search(admin, "rank").values_list("pk", flat=True)) == [
        patients[tier].pk for tier in expected_tiers
    ]
    assert list(appointments_for_global_search(admin, "rank").values_list("pk", flat=True)) == [
        appointments[tier].pk for tier in expected_tiers
    ]
    assert list(
        payment_receivables_for_global_search(admin, "rank").values_list("pk", flat=True)
    ) == [receivables[tier].pk for tier in expected_tiers]
    assert list(materials_for_global_search(admin, "rank").values_list("pk", flat=True)) == [
        materials[tier].pk for tier in expected_tiers
    ]


@pytest.mark.django_db
def test_per_group_limit_sets_has_more_and_returned_count() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN, first_name="Адмін")
    for index in range(6):
        Patient.objects.create(
            first_name=f"Ліміт {index}",
            last_name="Пошуку",
            phone=f"06712345{index:02d}",
        )

    response = authenticated_client(admin).get(
        "/api/v1/search",
        {"q": "ліміт", "types": "patients"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] == 5
    assert len(body["groups"][0]["items"]) == 5
    assert body["groups"][0]["has_more"] is True


@pytest.mark.django_db
def test_scope_is_applied_before_ranking_and_per_group_limit() -> None:
    owner = create_user(
        email="owner@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
    )
    foreign = create_user(
        email="foreign@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Ірина",
    )
    own = Patient.objects.create(
        first_name="Далекий needle результат",
        last_name="Власний",
        phone="0670000000",
        primary_podologist=owner,
    )
    for index in range(6):
        Patient.objects.create(
            first_name=f"Needle {index}",
            last_name="Чужий",
            phone=f"06800000{index:02d}",
            primary_podologist=foreign,
        )

    response = authenticated_client(owner).get(
        "/api/v1/search",
        {"q": "needle", "types": "patients"},
    )
    assert response.status_code == 200
    group = response.json()["groups"][0]
    assert [item["id"] for item in group["items"]] == [str(own.pk)]
    assert group["has_more"] is False


@pytest.mark.django_db
def test_patient_and_appointment_search_hydrate_only_safe_projection() -> None:
    fixture = domain_fixture()

    with CaptureQueriesContext(connection) as patient_queries:
        patient = patients_for_global_search(
            fixture["reception"],  # type: ignore[arg-type]
            "орбіта",
        ).get(pk=fixture["patient"].pk)  # type: ignore[union-attr]
        _ = (patient.display_name, patient.phone, patient.public_number)

    assert len(patient_queries) == 1
    patient_select = (
        patient_queries.captured_queries[0]["sql"]
        .lower()
        .split(
            ' from "patients_patient"',
            maxsplit=1,
        )[0]
    )
    assert '"patients_patient"."note"' not in patient_select
    assert '"patients_patient"."birth_date"' not in patient_select
    assert '"patients_patient"."email"' not in patient_select
    assert {
        "birth_date",
        "email",
        "note",
        "normalized_phone",
        "primary_podologist_id",
        "created_by_id",
        "created_at",
        "updated_at",
    } <= patient.get_deferred_fields()

    with CaptureQueriesContext(connection) as appointment_queries:
        appointment = appointments_for_global_search(
            fixture["reception"],  # type: ignore[arg-type]
            "орбіта",
        ).get(pk=fixture["appointment"].pk)  # type: ignore[union-attr]
        _ = (
            appointment.patient.display_name,
            appointment.specialist.display_name,
            appointment.status.label,
            appointment.service_name_snapshot,
            appointment.starts_at,
        )

    assert len(appointment_queries) == 1
    appointment_select = (
        appointment_queries.captured_queries[0]["sql"]
        .lower()
        .split(
            ' from "scheduling_appointment"',
            maxsplit=1,
        )[0]
    )
    assert '"scheduling_appointment"."complaints"' not in appointment_select
    assert '"patients_patient"."note"' not in appointment_select
    assert '"accounts_user"."password"' not in appointment_select
    assert set(appointment._state.fields_cache) == {"patient", "specialist", "status"}
    assert {
        "complaints",
        "comment",
        "cancellation_reason",
        "has_no_complaints",
        "service_color_snapshot",
        "room_label_snapshot",
    } <= appointment.get_deferred_fields()
    assert {
        "phone",
        "normalized_phone",
        "birth_date",
        "email",
        "note",
    } <= appointment.patient.get_deferred_fields()
    assert {
        "password",
        "phone",
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
    } <= appointment.specialist.get_deferred_fields()
    assert {
        "color",
        "manual_admin",
        "manual_reception",
        "manual_podologist",
        "version",
    } <= appointment.status.get_deferred_fields()


@pytest.mark.django_db
def test_material_search_prefetches_only_stock_projection_fields() -> None:
    fixture = domain_fixture()
    material = fixture["material"]
    MaterialLot.objects.create(
        material=material,  # type: ignore[arg-type]
        lot_number="SEARCH-SAFE-LOT",
        received_on=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=30),
        initial_quantity=5,
        current_quantity=4,
        purchase_price_minor=12_345,
        supplier_name="Sensitive supplier",
    )

    with CaptureQueriesContext(connection) as captured:
        result = materials_for_global_search(
            fixture["admin"],  # type: ignore[arg-type]
            "орбіта",
        ).get(pk=material.pk)  # type: ignore[union-attr]
        _ = (result.available_quantity, result.stock_status)
        lot = next(iter(result.lots.all()))

    assert len(captured) == 2
    material_select = (
        captured.captured_queries[0]["sql"]
        .lower()
        .split(
            ' from "inventory_material"',
            maxsplit=1,
        )[0]
    )
    lot_prefetch_sql = captured.captured_queries[1]["sql"].lower()
    assert '"inventory_material"."version"' not in material_select
    assert '"purchase_price_minor"' not in lot_prefetch_sql
    assert '"supplier_name"' not in lot_prefetch_sql
    assert {"version", "created_at", "updated_at"} <= result.get_deferred_fields()
    assert {
        "lot_number",
        "received_on",
        "initial_quantity",
        "purchase_price_minor",
        "supplier_name",
        "created_at",
    } <= lot.get_deferred_fields()


@pytest.mark.django_db
def test_paid_formatted_phone_is_searchable_by_digits_only() -> None:
    fixture = domain_fixture()
    reception = fixture["reception"]
    receivable = fixture["receivable"]
    open_cash_shift(actor=reception, correlation_id="search-phone-shift")  # type: ignore[arg-type]
    post_fixture_payment(
        actor=reception,  # type: ignore[arg-type]
        receivable=receivable,  # type: ignore[arg-type]
        correlation_id="search-phone-payment",
        idempotency_key="search-phone-payment-key",
    )

    response = authenticated_client(reception).get(  # type: ignore[arg-type]
        "/api/v1/search",
        {"q": "380671234567", "types": "payments"},
    )
    assert response.status_code == 200
    assert response.json()["groups"][0]["items"][0]["id"] == str(receivable.pk)  # type: ignore[union-attr]


@pytest.mark.django_db
def test_payment_search_prefetches_only_safe_item_context() -> None:
    fixture = domain_fixture()
    reception = fixture["reception"]
    open_cash_shift(actor=reception, correlation_id="search-hydration-shift")  # type: ignore[arg-type]
    post_fixture_payment(
        actor=reception,  # type: ignore[arg-type]
        receivable=fixture["receivable"],  # type: ignore[arg-type]
        correlation_id="search-hydration-payment",
        idempotency_key="search-hydration-payment-key",
    )

    with CaptureQueriesContext(connection) as captured:
        receivable = payment_receivables_for_global_search(
            reception,  # type: ignore[arg-type]
            "орбіта",
        ).get(pk=fixture["receivable"].pk)  # type: ignore[union-attr]
        payment = next(iter(receivable.payment_records.all()))
        _ = (
            receivable.amount_minor,
            receivable.status,
            receivable.visit.public_number,
            receivable.visit.completed_at,
            receivable.visit.patient.display_name,
            payment.patient_name_snapshot,
            payment.ledger_entry.public_number,
            payment.ledger_entry.payment_method,
        )

    assert len(captured) == 2
    search_sql = captured.captured_queries[0]["sql"].lower()
    search_select = search_sql.split(' from "billing_receivable"', maxsplit=1)[0]
    payment_prefetch_sql = captured.captured_queries[-1]["sql"].lower()
    assert "accounts_user" not in search_sql
    assert '"patients_patient"."note"' not in search_select
    assert '"visits_visit"."complaints"' not in search_select
    assert '"billing_receivable"."updated_at"' not in search_select
    assert 'inner join "billing_cashledgerentry"' in payment_prefetch_sql
    assert "billing_cashshift" not in payment_prefetch_sql
    assert "billing_refund" not in payment_prefetch_sql
    assert "visits_visitserviceline" not in payment_prefetch_sql
    assert set(receivable._state.fields_cache) == {"visit"}
    assert {"created_at", "updated_at"} <= receivable.get_deferred_fields()
    assert set(receivable.visit._state.fields_cache) == {"patient", "receivable"}
    assert {
        "appointment_id",
        "specialist_id",
        "status",
        "complaints",
        "objective_examination",
        "detected_conditions",
        "podologist_notes",
        "started_by_id",
    } <= receivable.visit.get_deferred_fields()
    assert {
        "phone",
        "normalized_phone",
        "birth_date",
        "email",
        "note",
    } <= receivable.visit.patient.get_deferred_fields()
    assert set(payment._state.fields_cache) == {"ledger_entry", "receivable"}
    assert {
        "comment",
        "patient_phone_snapshot",
        "services_snapshot",
        "services_search_snapshot",
    } <= payment.get_deferred_fields()
    assert "cash_shift_id" in payment.ledger_entry.get_deferred_fields()


@pytest.mark.django_db
def test_paid_payment_ranking_covers_snapshot_ledger_and_phone_tiers() -> None:
    fixture = domain_fixture()
    reception = fixture["reception"]
    receivable = fixture["receivable"]
    open_cash_shift(actor=reception, correlation_id="search-paid-rank-shift")  # type: ignore[arg-type]
    post_fixture_payment(
        actor=reception,  # type: ignore[arg-type]
        receivable=receivable,  # type: ignore[arg-type]
        correlation_id="search-paid-rank-payment",
        idempotency_key="search-paid-rank-payment-key",
    )
    payment = Payment.objects.select_related("ledger_entry").get(receivable=receivable)

    def rank_for(search: str) -> int:
        return (
            payment_receivables_for_global_search(
                reception,  # type: ignore[arg-type]
                search,
            )
            .filter(pk=receivable.pk)
            .annotate(exposed_rank=F("global_search_rank"))
            .values_list(
                "exposed_rank",
                flat=True,
            )
            .get()
        )

    assert rank_for(payment.ledger_entry.public_number.casefold()) == 0
    assert rank_for(payment.ledger_entry.public_number[:8].casefold()) == 1
    assert rank_for("380671234567") == 0
    assert rank_for(payment.patient_name_snapshot.casefold()) == 2


@pytest.mark.django_db
def test_exact_finance_resolver_is_typed_and_role_protected() -> None:
    fixture = domain_fixture()
    receivable = fixture["receivable"]
    url = f"/api/v1/finance/operations/PAYMENT/{receivable.pk}"  # type: ignore[union-attr]

    admin = authenticated_client(fixture["admin"]).get(url)  # type: ignore[arg-type]
    reception = authenticated_client(fixture["reception"]).get(url)  # type: ignore[arg-type]
    podologist = authenticated_client(fixture["owner"]).get(url)  # type: ignore[arg-type]
    unsupported = authenticated_client(fixture["admin"]).get(  # type: ignore[arg-type]
        f"/api/v1/finance/operations/REFUND/{receivable.pk}"  # type: ignore[union-attr]
    )
    missing = authenticated_client(fixture["admin"]).get(  # type: ignore[arg-type]
        f"/api/v1/finance/operations/PAYMENT/{uuid4()}"
    )

    assert admin.status_code == reception.status_code == 200
    assert admin.json()["id"] == str(receivable.pk)  # type: ignore[union-attr]
    assert admin.json()["type"] == "PAYMENT"
    assert admin.json()["payment"] is None
    assert podologist.status_code == 403
    assert unsupported.status_code == missing.status_code == 404


@pytest.mark.django_db
def test_openapi_publishes_search_contract_and_exact_finance_resolver() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    assert schema is not None
    search = schema["paths"]["/api/v1/search"]["get"]
    detail = schema["paths"]["/api/v1/finance/operations/{operation_type}/{operation_id}"]["get"]
    assert search["operationId"] == "global_search_list"
    assert detail["operationId"] == "finance_operation_retrieve"
    parameters = {parameter["name"]: parameter for parameter in search["parameters"]}
    assert parameters["q"]["required"] is True
    assert parameters["q"]["schema"]["minLength"] == 2
    assert parameters["q"]["schema"]["maxLength"] == 100
    components = schema["components"]["schemas"]
    assert set(components["GlobalSearchItem"]["required"]) == {
        "type",
        "id",
        "title",
        "subtitle",
        "meta",
        "deep_link",
    }
    assert components["GlobalSearchGroup"]["properties"]["type"]["$ref"].endswith(
        "/GlobalSearchGroupTypeEnum"
    )
