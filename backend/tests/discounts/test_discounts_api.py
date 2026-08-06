from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import UserRole
from apps.audit.models import AuditEvent
from apps.discounts.models import Discount, LoyaltyPolicy, ProtectedDiscountError
from tests.billing.test_payments_api import authenticated_client, create_user


@pytest.mark.django_db
def test_admin_manages_discount_catalog_with_version_audit_and_no_delete() -> None:
    admin = create_user(email="discount-admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    created = client.post(
        "/api/v1/discounts",
        {"name": "Постійний клієнт", "percent": 10},
        format="json",
    )
    assert created.status_code == 201, created.json()
    discount_id = created.json()["id"]
    assert created.json()["version"] == 1

    renamed = client.patch(
        f"/api/v1/discounts/{discount_id}",
        {"name": "Постійний клієнт 10%", "version": 1},
        format="json",
    )
    assert renamed.status_code == 200, renamed.json()
    assert renamed.json()["version"] == 2

    stale = client.patch(
        f"/api/v1/discounts/{discount_id}",
        {"percent": 15, "version": 1},
        format="json",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"

    deactivated = client.patch(
        f"/api/v1/discounts/{discount_id}",
        {"is_active": False, "version": 2},
        format="json",
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.delete(f"/api/v1/discounts/{discount_id}").status_code == 405
    with pytest.raises(ProtectedDiscountError):
        Discount.objects.get(pk=discount_id).delete()

    actions = list(
        AuditEvent.objects.filter(object_id=discount_id)
        .order_by("occurred_at")
        .values_list("action", flat=True)
    )
    assert actions == [
        "settings.discount_created",
        "settings.discount_updated",
        "settings.discount_deactivated",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("percent", [0, 100])
def test_discount_percent_rejects_zero_and_one_hundred(percent: int) -> None:
    admin = create_user(email=f"discount-{percent}@example.test", role=UserRole.ADMIN)
    response = authenticated_client(admin).post(
        "/api/v1/discounts",
        {"name": f"Invalid {percent}", "percent": percent},
        format="json",
    )
    assert response.status_code == 422
    assert "percent" in response.json()["fields"]


@pytest.mark.django_db
def test_discount_db_guard_and_case_insensitive_name_conflict() -> None:
    first = Discount.objects.create(name="Лояльність", percent=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Discount.objects.create(name="лояльність", percent=99)
    with pytest.raises(IntegrityError), transaction.atomic():
        Discount.objects.create(name="Invalid", percent=100)
    assert Discount.objects.get(pk=first.pk).percent == 1


@pytest.mark.django_db
def test_non_admin_sees_only_active_discounts_and_cannot_mutate() -> None:
    active = Discount.objects.create(name="Активна", percent=5)
    Discount.objects.create(name="Неактивна", percent=7, is_active=False)
    reception = create_user(email="discount-reception@example.test", role=UserRole.RECEPTION)
    client = authenticated_client(reception)

    listed = client.get("/api/v1/discounts", {"status": "all"})
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["discounts"]] == [str(active.pk)]
    assert (
        client.post(
            "/api/v1/discounts",
            {"name": "Forbidden", "percent": 5},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/discounts/{active.pk}",
            {"percent": 6, "version": 1},
            format="json",
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_admin_configures_singleton_loyalty_policy_and_active_discount_guard() -> None:
    admin = create_user(email="loyalty-admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    discount = Discount.objects.create(name="Кожен п'ятий", percent=10)

    initial = client.get("/api/v1/loyalty-policy")
    assert initial.status_code == 200
    assert initial.json()["is_active"] is False
    assert initial.json()["discount"] is None

    configured = client.patch(
        "/api/v1/loyalty-policy",
        {
            "is_active": True,
            "every_n": 5,
            "discount_id": str(discount.pk),
            "version": initial.json()["version"],
        },
        format="json",
    )
    assert configured.status_code == 200, configured.json()
    assert configured.json()["is_active"] is True
    assert configured.json()["every_n"] == 5
    assert configured.json()["discount"]["id"] == str(discount.pk)
    started_at = configured.json()["started_at"]

    changed = client.patch(
        "/api/v1/loyalty-policy",
        {"every_n": 3, "version": configured.json()["version"]},
        format="json",
    )
    assert changed.status_code == 200
    assert changed.json()["started_at"] == started_at

    blocked = client.patch(
        f"/api/v1/discounts/{discount.pk}",
        {"is_active": False, "version": discount.version},
        format="json",
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "discount_used_by_active_loyalty"
    assert LoyaltyPolicy.objects.get().discount_id == discount.pk


@pytest.mark.django_db
def test_loyalty_policy_requires_active_discount_and_admin_role() -> None:
    admin = create_user(email="loyalty-validation@example.test", role=UserRole.ADMIN)
    reception = create_user(email="loyalty-forbidden@example.test", role=UserRole.RECEPTION)
    inactive = Discount.objects.create(name="Inactive loyalty", percent=10, is_active=False)
    policy = LoyaltyPolicy.objects.get()

    missing = authenticated_client(admin).patch(
        "/api/v1/loyalty-policy",
        {"is_active": True, "version": policy.version},
        format="json",
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "loyalty_discount_required"

    unavailable = authenticated_client(admin).patch(
        "/api/v1/loyalty-policy",
        {"discount_id": str(inactive.pk), "version": policy.version},
        format="json",
    )
    assert unavailable.status_code == 409
    assert unavailable.json()["code"] == "discount_unavailable"
    assert authenticated_client(reception).get("/api/v1/loyalty-policy").status_code == 403
    assert authenticated_client(admin).get(f"/api/v1/discounts/{uuid4()}").status_code == 404
