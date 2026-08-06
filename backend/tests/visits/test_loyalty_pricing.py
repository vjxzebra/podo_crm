from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connections

from apps.accounts.models import User, UserRole
from apps.billing.models import (
    CashLedgerEntry,
    DiscountSource,
    Payment,
    PricingState,
    Receivable,
    ReceivableStatus,
    VisitPricing,
)
from apps.discounts.models import (
    Discount,
    LoyaltyPolicy,
    PatientLoyaltyState,
    VisitLoyaltyEvent,
)
from apps.scheduling.models import Appointment
from apps.visits.models import Visit
from tests.scheduling.test_create_appointment import KYIV, appointment_payload
from tests.visits.test_visit_finish import _finish, _finish_payload, _visit_with_materials
from tests.visits.test_visit_start_and_draft import (
    arrived_appointment,
    authenticated_client,
    create_user,
    start,
)


def _additional_arrived(*, actor: User, source: Appointment, day_offset: int) -> Appointment:
    starts_at = datetime(2026, 8, 3, 10, 0, tzinfo=KYIV) + timedelta(days=7 * day_offset)
    response = authenticated_client(actor).post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=source.specialist,
            service=source.service,
            room=source.room,
            patient=source.patient,
            starts_at=starts_at,
        ),
        format="json",
    )
    assert response.status_code == 201, response.json()
    appointment = Appointment.objects.get(pk=response.json()["id"])
    appointment.status_id = "ARRIVED"
    appointment.version += 1
    appointment.save(update_fields=("status", "version", "updated_at"))
    return appointment


def _finish_appointment(
    *,
    actor: User,
    appointment: Appointment,
    key: str,
    discount: Discount | None = None,
):
    visit_response = start(authenticated_client(actor), appointment)
    assert visit_response.status_code in {200, 201}, visit_response.json()
    visit = Visit.objects.get(pk=visit_response.json()["id"])
    payload = _finish_payload(version=visit.version, recommendation="")
    if discount is not None:
        payload["discount_id"] = str(discount.pk)
    response = _finish(
        authenticated_client(actor),
        str(visit.pk),
        payload,
        key=key,
    )
    assert response.status_code == 201, response.json()
    return visit, response


def _activate_policy(*, every_n: int, discount: Discount) -> LoyaltyPolicy:
    policy, _ = LoyaltyPolicy.objects.get_or_create(key="default")
    policy.is_active = True
    policy.every_n = every_n
    policy.discount = discount
    policy.started_at = datetime(2026, 8, 1, 9, 0, tzinfo=KYIV)
    policy.save()
    return policy


@pytest.mark.django_db
def test_every_n_loyalty_uses_new_successful_finish_ordinals_and_replay_is_safe() -> None:
    admin = create_user(email="ordinal-admin@example.test", role=UserRole.ADMIN)
    first_appointment = arrived_appointment(actor=admin)
    second_appointment = _additional_arrived(actor=admin, source=first_appointment, day_offset=1)
    loyalty = Discount.objects.create(name="Кожен другий", percent=10)
    _activate_policy(every_n=2, discount=loyalty)

    first_visit, first = _finish_appointment(
        actor=admin,
        appointment=first_appointment,
        key="loyalty-first",
    )
    second_visit, second = _finish_appointment(
        actor=admin,
        appointment=second_appointment,
        key="loyalty-second",
    )
    replay = _finish(
        authenticated_client(admin),
        str(second_visit.pk),
        _finish_payload(version=second_visit.version, recommendation=""),
        key="loyalty-second",
    )

    assert first.json()["pricing"]["discount_id"] is None
    assert first.json()["pricing"]["net_minor"] == first_appointment.service.price_minor
    assert second.json()["pricing"]["discount_id"] == str(loyalty.pk)
    assert second.json()["pricing"]["discount_source"] == DiscountSource.LOYALTY
    assert second.json()["pricing"]["discount_amount_minor"] == 15_000
    assert second.json()["pricing"]["net_minor"] == 135_000
    assert second.json()["visit"]["total_minor"] == 135_000
    assert second.json()["receivable"]["amount_minor"] == 135_000
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    state = PatientLoyaltyState.objects.get(patient=first_appointment.patient)
    assert state.completed_count == 2
    assert list(
        VisitLoyaltyEvent.objects.filter(patient=first_appointment.patient)
        .order_by("sequence_number")
        .values_list("sequence_number", "eligible")
    ) == [(1, False), (2, True)]
    assert VisitPricing.objects.get(visit=first_visit).discount_id is None
    assert VisitPricing.objects.get(visit=second_visit).discount_id == loyalty.pk


@pytest.mark.django_db
def test_manual_podologist_discount_sets_non_n_visit_and_replaces_nth_loyalty() -> None:
    admin = create_user(email="manual-admin@example.test", role=UserRole.ADMIN)
    first_appointment = arrived_appointment(actor=admin)
    second_appointment = _additional_arrived(actor=admin, source=first_appointment, day_offset=1)
    loyalty = Discount.objects.create(name="Loyalty 5", percent=5)
    manual = Discount.objects.create(name="Manual 20", percent=20)
    _activate_policy(every_n=2, discount=loyalty)

    _, first = _finish_appointment(
        actor=admin,
        appointment=first_appointment,
        key="manual-non-n",
        discount=manual,
    )
    second_visit, second = _finish_appointment(
        actor=admin,
        appointment=second_appointment,
        key="manual-nth",
        discount=manual,
    )

    assert first.json()["pricing"]["discount_source"] == DiscountSource.PODOLOGIST
    assert second.json()["pricing"]["discount_id"] == str(manual.pk)
    assert second.json()["pricing"]["discount_percent"] == 20
    assert second.json()["pricing"]["discount_source"] == DiscountSource.PODOLOGIST
    event = VisitLoyaltyEvent.objects.get(visit=second_visit)
    assert event.eligible is True
    assert event.discount_id == loyalty.pk
    assert PatientLoyaltyState.objects.get(patient=first_appointment.patient).completed_count == 2


@pytest.mark.django_db
def test_inactive_policy_pauses_counter_and_reenable_resumes_progress() -> None:
    admin = create_user(email="pause-admin@example.test", role=UserRole.ADMIN)
    first_appointment = arrived_appointment(actor=admin)
    paused_appointment = _additional_arrived(actor=admin, source=first_appointment, day_offset=1)
    resumed_appointment = _additional_arrived(actor=admin, source=first_appointment, day_offset=2)
    loyalty = Discount.objects.create(name="Pause loyalty", percent=10)
    policy = _activate_policy(every_n=2, discount=loyalty)

    _finish_appointment(actor=admin, appointment=first_appointment, key="before-pause")
    policy.is_active = False
    policy.save(update_fields=("is_active", "updated_at"))
    paused_visit, paused = _finish_appointment(
        actor=admin,
        appointment=paused_appointment,
        key="during-pause",
    )
    assert paused.json()["pricing"]["discount_id"] is None
    assert not VisitLoyaltyEvent.objects.filter(visit=paused_visit).exists()
    assert PatientLoyaltyState.objects.get(patient=first_appointment.patient).completed_count == 1

    policy.is_active = True
    policy.save(update_fields=("is_active", "updated_at"))
    _, resumed = _finish_appointment(
        actor=admin,
        appointment=resumed_appointment,
        key="after-pause",
    )
    assert resumed.json()["pricing"]["discount_id"] == str(loyalty.pk)
    assert PatientLoyaltyState.objects.get(patient=first_appointment.patient).completed_count == 2


@pytest.mark.django_db
def test_zero_gross_ignores_discount_and_auto_settles_without_payment_or_ledger() -> None:
    admin = create_user(email="zero-pricing-admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    appointment.service.price_minor = 0
    appointment.service.save(update_fields=("price_minor", "updated_at"))
    loyalty = Discount.objects.create(name="Zero loyalty", percent=99)
    _activate_policy(every_n=1, discount=loyalty)

    visit, response = _finish_appointment(
        actor=admin,
        appointment=appointment,
        key="zero-pricing",
        discount=loyalty,
    )

    pricing = VisitPricing.objects.get(visit=visit)
    assert response.json()["pricing"]["gross_minor"] == 0
    assert response.json()["pricing"]["discount_id"] is None
    assert pricing.state == PricingState.SETTLED
    assert pricing.net_minor == 0
    assert response.json()["receivable"]["status"] == ReceivableStatus.PAID
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_failed_finish_rolls_back_loyalty_counter_event_and_pricing() -> None:
    admin = create_user(email="loyalty-rollback-admin@example.test", role=UserRole.ADMIN)
    appointment, visit, _ = _visit_with_materials(admin=admin, quantities=("1.000",))
    loyalty = Discount.objects.create(name="Rollback loyalty", percent=10)
    _activate_policy(every_n=1, discount=loyalty)

    with patch(
        "apps.visits.finish_services.StockMovement.objects.create",
        side_effect=RuntimeError("fault after loyalty allocation"),
    ):
        response = _finish(
            authenticated_client(admin),
            str(visit.pk),
            _finish_payload(version=visit.version, recommendation=""),
            key="loyalty-rollback",
        )

    assert response.status_code == 500
    visit.refresh_from_db()
    appointment.refresh_from_db()
    assert visit.status == "DRAFT"
    assert appointment.status_id == "IN_PROGRESS"
    assert not PatientLoyaltyState.objects.filter(patient=appointment.patient).exists()
    assert not VisitLoyaltyEvent.objects.filter(visit=visit).exists()
    assert not VisitPricing.objects.filter(visit=visit).exists()
    assert not Receivable.objects.filter(visit=visit).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_finishes_for_one_patient_serialize_loyalty_ordinals() -> None:
    admin = create_user(email="loyalty-race-admin@example.test", role=UserRole.ADMIN)
    first_appointment = arrived_appointment(actor=admin)
    second_appointment = _additional_arrived(
        actor=admin,
        source=first_appointment,
        day_offset=1,
    )
    loyalty = Discount.objects.create(name="Race loyalty", percent=10)
    _activate_policy(every_n=2, discount=loyalty)
    visits = [
        Visit.objects.get(pk=start(authenticated_client(admin), appointment).json()["id"])
        for appointment in (first_appointment, second_appointment)
    ]
    barrier = Barrier(2)

    def finish(index: int) -> tuple[int, str]:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        visit = Visit.objects.get(pk=visits[index].pk)
        barrier.wait(timeout=5)
        try:
            response = _finish(
                authenticated_client(actor),
                str(visit.pk),
                _finish_payload(version=visit.version, recommendation=""),
                key=f"loyalty-race-{index}",
            )
            return response.status_code, str(visit.pk)
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(finish, range(2)))

    assert sorted(status_code for status_code, _ in results) == [201, 201]
    state = PatientLoyaltyState.objects.get(patient=first_appointment.patient)
    assert state.completed_count == 2
    assert state.version == 3
    events = list(
        VisitLoyaltyEvent.objects.filter(patient=first_appointment.patient)
        .order_by("sequence_number")
        .values_list("visit_id", "sequence_number", "eligible")
    )
    assert [sequence for _, sequence, _ in events] == [1, 2]
    assert [eligible for _, _, eligible in events] == [False, True]
    assert {str(visit_id) for visit_id, _, _ in events} == {str(visit.pk) for visit in visits}
    pricings = list(VisitPricing.objects.filter(visit__in=visits))
    assert len(pricings) == 2
    assert sum(pricing.discount_id == loyalty.pk for pricing in pricings) == 1
    assert sum(pricing.discount_source == DiscountSource.LOYALTY for pricing in pricings) == 1


@pytest.mark.django_db
def test_visit_read_model_previews_loyalty_before_finish_and_reports_event_after() -> None:
    admin = create_user(email="preview-admin@example.test", role=UserRole.ADMIN)
    first_appointment = arrived_appointment(actor=admin)
    second_appointment = _additional_arrived(actor=admin, source=first_appointment, day_offset=1)
    loyalty = Discount.objects.create(name="Кожен другий", percent=10)
    _activate_policy(every_n=2, discount=loyalty)
    client = authenticated_client(admin)

    first_visit_response = start(client, first_appointment)
    first_visit = Visit.objects.get(pk=first_visit_response.json()["id"])
    draft_preview = client.get(f"/api/v1/visits/{first_visit.pk}").json()["loyalty"]

    assert draft_preview == {
        "is_active": True,
        "every_n": 2,
        "visit_number": 1,
        "eligible": False,
        "discount": None,
    }
    # The preview must not advance the authoritative counter.
    assert not PatientLoyaltyState.objects.filter(patient=first_appointment.patient).exists()

    _finish(
        client,
        str(first_visit.pk),
        _finish_payload(version=first_visit.version, recommendation=""),
        key="preview-first",
    )
    second_visit_response = start(client, second_appointment)
    second_visit = Visit.objects.get(pk=second_visit_response.json()["id"])
    eligible_preview = client.get(f"/api/v1/visits/{second_visit.pk}").json()["loyalty"]

    assert eligible_preview["visit_number"] == 2
    assert eligible_preview["eligible"] is True
    assert eligible_preview["discount"] == {
        "id": str(loyalty.pk),
        "name": "Кожен другий",
        "percent": 10,
    }

    _finish(
        client,
        str(second_visit.pk),
        _finish_payload(version=second_visit.version, recommendation=""),
        key="preview-second",
    )
    settled_preview = client.get(f"/api/v1/visits/{second_visit.pk}").json()["loyalty"]

    # A finished visit reports its immutable event, not a fresh forecast.
    assert settled_preview["visit_number"] == 2
    assert settled_preview["eligible"] is True
    assert settled_preview["discount"]["percent"] == 10
    assert client.get(f"/api/v1/visits/{first_visit.pk}").json()["loyalty"] == {
        "is_active": True,
        "every_n": 2,
        "visit_number": 1,
        "eligible": False,
        "discount": None,
    }


@pytest.mark.django_db
def test_visit_loyalty_preview_reports_inactive_policy_without_forecast() -> None:
    admin = create_user(email="inactive-preview@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    client = authenticated_client(admin)
    visit_response = start(client, appointment)
    visit = Visit.objects.get(pk=visit_response.json()["id"])

    preview = client.get(f"/api/v1/visits/{visit.pk}").json()["loyalty"]

    assert preview["is_active"] is False
    assert preview["eligible"] is False
    assert preview["visit_number"] is None
    assert preview["discount"] is None
