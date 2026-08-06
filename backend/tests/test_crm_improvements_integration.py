from datetime import datetime, timedelta
from io import BytesIO

import pytest
from pypdf import PdfReader

from apps.accounts.models import UserRole
from apps.billing.models import Payment, PaymentMethod, Receivable
from apps.clinic.models import Service
from apps.discounts.models import Discount, PatientLoyaltyState, VisitLoyaltyEvent
from apps.scheduling.models import Appointment
from tests.billing.test_cash_shift_api import post_open
from tests.billing.test_payments_api import post_payment
from tests.scheduling.test_create_appointment import KYIV, appointment_payload
from tests.visits.test_loyalty_pricing import _activate_policy, _finish_appointment
from tests.visits.test_visit_start_and_draft import (
    arrived_appointment,
    authenticated_client,
    create_user,
)


def _additional_arrived_appointment(
    *,
    actor,
    source: Appointment,
    week_offset: int,
    services: list[Service] | None = None,
) -> Appointment:
    payload = appointment_payload(
        specialist=source.specialist,
        service=source.service,
        room=source.room,
        patient=source.patient,
        starts_at=datetime(2026, 8, 3, 10, 0, tzinfo=KYIV) + timedelta(days=7 * week_offset),
    )
    if services is not None:
        payload.pop("service_id")
        payload["service_ids"] = [str(service.pk) for service in services]
    response = authenticated_client(actor).post(
        "/api/v1/appointments",
        payload,
        format="json",
    )
    assert response.status_code == 201, response.json()
    appointment = Appointment.objects.get(pk=response.json()["id"])
    appointment.status_id = "ARRIVED"
    appointment.version += 1
    appointment.save(update_fields=("status", "version", "updated_at"))
    return appointment


@pytest.mark.django_db(transaction=True)
def test_every_fifth_multi_service_visit_override_receipt_and_cash_carry_forward() -> None:
    admin = create_user(email="flow-admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="flow-reception@example.test", role=UserRole.RECEPTION)
    next_reception = create_user(
        email="flow-next-reception@example.test",
        role=UserRole.RECEPTION,
    )
    first_appointment = arrived_appointment(actor=admin)
    additional_service = Service.objects.create(
        code="FLOW-SECOND",
        name="Додаткова обробка",
        duration_minutes=30,
        price_minor=80_000,
        color="#7C3AED",
    )
    loyalty_discount = Discount.objects.create(name="Кожен п'ятий", percent=10)
    reception_discount = Discount.objects.create(name="Рецепція 20", percent=20)
    _activate_policy(every_n=5, discount=loyalty_discount)

    appointments = [first_appointment]
    appointments.extend(
        _additional_arrived_appointment(
            actor=admin,
            source=first_appointment,
            week_offset=index,
            services=([first_appointment.service, additional_service] if index == 3 else None),
        )
        for index in range(4)
    )
    finish_results = [
        _finish_appointment(
            actor=admin,
            appointment=appointment,
            key=f"flow-finish-{index}",
        )
        for index, appointment in enumerate(appointments, start=1)
    ]

    fifth_visit, fifth_response = finish_results[-1]
    fifth_pricing = fifth_response.json()["pricing"]
    assert fifth_pricing["gross_minor"] == 230_000
    assert fifth_pricing["discount_id"] == str(loyalty_discount.pk)
    assert fifth_pricing["discount_percent"] == 10
    assert fifth_pricing["discount_amount_minor"] == 23_000
    assert fifth_pricing["net_minor"] == 207_000
    assert PatientLoyaltyState.objects.get(patient=first_appointment.patient).completed_count == 5
    fifth_event = VisitLoyaltyEvent.objects.get(visit=fifth_visit)
    assert (fifth_event.sequence_number, fifth_event.eligible) == (5, True)

    reception_client = authenticated_client(reception)
    opened = post_open(reception_client)
    assert opened.status_code == 201, opened.json()
    receivable = Receivable.objects.get(visit=fifth_visit)
    paid = post_payment(
        reception_client,
        receivable,
        key="flow-payment",
        payment_method=PaymentMethod.CASH,
        discount_action="SET",
        discount_id=str(reception_discount.pk),
    )
    assert paid.status_code == 201, paid.json()
    paid_pricing = paid.json()["operation"]["pricing"]
    assert paid_pricing["gross_minor"] == 230_000
    assert paid_pricing["discount_id"] == str(reception_discount.pk)
    assert paid_pricing["discount_percent"] == 20
    assert paid_pricing["discount_amount_minor"] == 46_000
    assert paid_pricing["net_minor"] == 184_000

    payment = Payment.objects.get(receivable=receivable)
    reception_discount.name = "Перейменована після оплати"
    reception_discount.is_active = False
    reception_discount.version += 1
    reception_discount.save()
    payment.refresh_from_db()
    assert payment.discount_name_snapshot == "Рецепція 20"
    assert payment.net_total_minor_snapshot == 184_000

    receipt = reception_client.get(
        f"/api/v1/payments/{payment.pk}/receipt",
        HTTP_ACCEPT="application/pdf",
    )
    assert receipt.status_code == 200
    reader = PdfReader(BytesIO(receipt.content))
    assert len(reader.pages) == 2
    receipt_text = reader.pages[0].extract_text()
    recommendation_text = reader.pages[1].extract_text()
    assert "Рецепція 20 (20%)" in receipt_text
    assert "1 840,00 грн" in receipt_text
    assert "Рекомендована дата наступного візиту" in recommendation_text

    shift = opened.json()
    closed = reception_client.post(
        f"/api/v1/cash-shifts/{shift['id']}/close",
        {
            "actual_cash_minor": 184_000,
            "expected_operations_count": 1,
            "cash_count_confirmed": True,
            "comment": "",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="flow-close",
    )
    assert closed.status_code == 201, closed.json()
    carried = post_open(authenticated_client(next_reception))
    assert carried.status_code == 201, carried.json()
    assert carried.json()["opening_cash_minor"] == 184_000
    assert carried.json()["opening_basis"] == "CARRY_FORWARD"
    assert carried.json()["opening_source_shift"]["id"] == shift["id"]
