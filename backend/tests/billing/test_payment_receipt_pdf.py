from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from drf_spectacular.generators import SchemaGenerator
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.billing.models import CashShift, Payment, PaymentMethod
from apps.clinic.models import ClinicProfile
from apps.visits.models import VisitRecommendation
from tests.billing.test_payments_api import (
    authenticated_client,
    completed_receivable,
    create_user,
    post_payment,
)


def _paid_receipt(*, payment_method: str = PaymentMethod.CARD):
    reception = create_user(email="receipt-reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=reception)
    receivable = completed_receivable(service_name="Медичний педикюр")
    VisitRecommendation.objects.create(
        visit=receivable.visit,
        author=receivable.visit.specialist,
        text="Щодня наносити доглядовий крем. Повторний огляд через 4 тижні.",
    )
    ClinicProfile.objects.update_or_create(
        key="clinic",
        defaults={
            "name": "Подологічний кабінет «Подорія»",
            "phone": "+380 67 111 22 33",
            "email": "clinic@example.test",
            "address": "м. Львів, вул. Тестова, 10",
        },
    )
    create_response = post_payment(
        authenticated_client(reception),
        receivable,
        payment_method=payment_method,
        comment="Оплачено на рецепції",
    )
    assert create_response.status_code == 201, create_response.json()
    payment = Payment.objects.get(pk=create_response.json()["operation"]["payment"]["id"])
    return reception, payment


@pytest.mark.django_db
def test_receipt_is_two_page_cyrillic_a4_pdf_from_payment_snapshots() -> None:
    reception, payment = _paid_receipt()

    response = authenticated_client(reception).get(
        f"/api/v1/payments/{payment.pk}/receipt",
        HTTP_ACCEPT="application/pdf",
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == (
        f'attachment; filename="payment-receipt-{payment.ledger_entry.public_number}.pdf"'
    )
    assert response["Cache-Control"] == "private, no-store"
    assert response.content.startswith(b"%PDF-")

    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) == 2
    width = float(reader.pages[0].mediabox.width)
    height = float(reader.pages[0].mediabox.height)
    assert width == pytest.approx(595.28, abs=0.2)
    assert height == pytest.approx(841.89, abs=0.2)

    first_page = reader.pages[0].extract_text()
    second_page = reader.pages[1].extract_text()
    assert "КВИТАНЦІЯ ПРО ОПЛАТУ" in first_page
    assert "НЕ Є ФІСКАЛЬНИМ ЧЕКОМ" in first_page
    assert payment.ledger_entry.public_number in first_page
    assert "Марія Бондар" in first_page
    assert "Олена Бойко" in first_page
    assert "Медичний педикюр" in first_page
    assert "1 450,00 грн" in first_page
    assert "Картка" in first_page
    assert "БЛАНК РЕКОМЕНДАЦІЙ" in second_page
    assert "Щодня наносити доглядовий крем" in second_page
    assert "скарг" not in (first_page + second_page).lower()


@pytest.mark.django_db
def test_receipt_supports_inline_print_and_survives_unavailable_optional_logo() -> None:
    reception, payment = _paid_receipt()
    ClinicProfile.objects.filter(key="clinic").update(
        logo_object_key="clinic/logo/missing.png",
        logo_content_type="image/png",
        logo_size=100,
    )

    with patch(
        "apps.billing.receipts.clinic_storage.get_private_object",
        side_effect=RuntimeError("object storage unavailable"),
    ):
        response = authenticated_client(reception).get(
            f"/api/v1/payments/{payment.pk}/receipt",
            {"disposition": "inline"},
            HTTP_ACCEPT="application/pdf",
        )

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("inline;")
    assert response.content.startswith(b"%PDF-")


@pytest.mark.django_db
def test_receipt_is_role_scoped_and_validates_disposition() -> None:
    reception, payment = _paid_receipt()
    podologist = create_user(
        email="receipt-podologist@example.test",
        role=UserRole.PODOLOGIST,
    )

    assert APIClient().get(f"/api/v1/payments/{payment.pk}/receipt").status_code == 401
    assert (
        authenticated_client(podologist).get(f"/api/v1/payments/{payment.pk}/receipt").status_code
        == 403
    )
    assert (
        authenticated_client(reception).get(f"/api/v1/payments/{uuid4()}/receipt").status_code
        == 404
    )
    invalid = authenticated_client(reception).get(
        f"/api/v1/payments/{payment.pk}/receipt",
        {"disposition": "popup"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_receipt_disposition"


@pytest.mark.django_db
def test_receipt_openapi_exposes_binary_pdf_contract() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    operation = schema["paths"]["/api/v1/payments/{payment_id}/receipt"]["get"]

    disposition = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "disposition"
    )
    assert set(disposition["schema"]["enum"]) == {"attachment", "inline"}
    assert "application/pdf" in operation["responses"]["200"]["content"]
