import pytest

from apps.accounts.models import UserRole
from apps.billing.models import CashShift, Payment, VisitPricing
from apps.discounts.models import Discount
from tests.billing.test_payments_api import (
    authenticated_client,
    completed_receivable,
    create_user,
    post_payment,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("gross_minor", "percent", "discount_minor", "net_minor"),
    [
        (1, 1, 0, 1),
        (1, 99, 0, 1),
        (101, 1, 1, 100),
        (101, 99, 99, 2),
    ],
)
def test_reception_discount_rounds_down_to_whole_minor_units(
    gross_minor: int,
    percent: int,
    discount_minor: int,
    net_minor: int,
) -> None:
    actor = create_user(
        email=f"rounding-{gross_minor}-{percent}@example.test",
        role=UserRole.RECEPTION,
    )
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable(amount_minor=gross_minor)
    discount = Discount.objects.create(
        name=f"Округлення {gross_minor}-{percent}",
        percent=percent,
    )

    response = post_payment(
        authenticated_client(actor),
        receivable,
        key=f"rounding-{gross_minor}-{percent}",
        discount_action="SET",
        discount_id=str(discount.pk),
    )

    assert response.status_code == 201, response.json()
    assert response.json()["operation"]["pricing"]["discount_amount_minor"] == discount_minor
    assert response.json()["operation"]["pricing"]["net_minor"] == net_minor
    pricing = VisitPricing.objects.get(visit_id=receivable.visit_id)
    payment = Payment.objects.get(receivable=receivable)
    assert pricing.discount_amount_minor == discount_minor
    assert pricing.net_minor == net_minor
    assert payment.discount_amount_minor_snapshot == discount_minor
    assert payment.net_total_minor_snapshot == net_minor
