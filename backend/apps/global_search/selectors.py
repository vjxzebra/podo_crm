from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User
from apps.billing.models import PaymentMethod, Receivable, ReceivableStatus
from apps.billing.selectors import payment_receivables_for_global_search
from apps.global_search.serializers import GLOBAL_SEARCH_GROUP_TYPES
from apps.inventory.models import Material, StockStatus
from apps.inventory.selectors import materials_for_global_search
from apps.patients.models import Patient
from apps.patients.selectors import patients_for_global_search
from apps.scheduling.models import Appointment
from apps.scheduling.selectors import appointments_for_global_search

GLOBAL_SEARCH_RESULT_LIMIT = 5


def _can_search_appointments(actor: User) -> bool:
    return has_scope(actor, AccessScope.CALENDAR_OWN) or has_scope(
        actor,
        AccessScope.CALENDAR_SHARED,
    )


def _allowed_categories(actor: User) -> frozenset[str]:
    allowed: set[str] = set()
    if has_scope(actor, AccessScope.PATIENT_SAFE):
        allowed.add("patients")
    if _can_search_appointments(actor):
        allowed.add("appointments")
    if has_scope(actor, AccessScope.FINANCE):
        allowed.add("payments")
    if has_scope(actor, AccessScope.INVENTORY):
        allowed.add("materials")
    return frozenset(allowed)


def _minor_to_hryvnia(amount_minor: int) -> str:
    whole, fraction = divmod(amount_minor, 100)
    grouped = f"{whole:,}".replace(",", " ")
    suffix = f",{fraction:02d}" if fraction else ""
    return f"{grouped}{suffix} ₴"


def _patient_item(patient: Patient) -> dict[str, Any]:
    return {
        "type": "patient",
        "id": patient.pk,
        "title": patient.display_name,
        "subtitle": patient.phone,
        "meta": patient.public_number,
        "deep_link": f"/patients/{patient.pk}/overview",
    }


def _appointment_item(appointment: Appointment) -> dict[str, Any]:
    starts_at = timezone.localtime(appointment.starts_at).strftime("%d.%m.%Y, %H:%M")
    return {
        "type": "appointment",
        "id": appointment.pk,
        "title": f"{appointment.patient.display_name} · {starts_at}",
        "subtitle": (
            f"{appointment.service_name_snapshot} · {appointment.specialist.display_name}"
        ),
        "meta": f"{appointment.public_number} · {appointment.status.label}",
        "deep_link": f"/calendar?appointment={appointment.pk}",
    }


def _payment_item(receivable: Receivable) -> dict[str, Any]:
    payment = next(iter(receivable.payment_records.all()), None)
    if payment is None:
        patient_name = receivable.visit.patient.display_name
        public_number = receivable.visit.public_number
        method_label = "Без касової операції"
    else:
        patient_name = payment.patient_name_snapshot
        public_number = payment.ledger_entry.public_number
        method_label = PaymentMethod(payment.ledger_entry.payment_method).label
    status_label = ReceivableStatus(receivable.status).label
    return {
        "type": "payment",
        "id": receivable.pk,
        "title": patient_name,
        "subtitle": f"{_minor_to_hryvnia(receivable.amount_minor)} · {status_label}",
        "meta": f"{public_number} · {method_label}",
        "deep_link": f"/finance?operation=PAYMENT:{receivable.pk}",
    }


def _material_item(material: Material) -> dict[str, Any]:
    state = "Активний" if material.is_active else "Неактивний"
    stock_label = StockStatus(material.stock_status).label
    available = f"{material.available_quantity.normalize():f}"
    return {
        "type": "material",
        "id": material.pk,
        "title": material.name,
        "subtitle": f"ART {material.sku} · {material.category}",
        "meta": f"{available} {material.unit} · {stock_label} · {state}",
        "deep_link": f"/inventory?material={material.pk}",
    }


SearchFactory = Callable[[User, str], QuerySet[Any]]
ItemFactory = Callable[[Any], dict[str, Any]]

_CATEGORY_HANDLERS: dict[str, tuple[SearchFactory, ItemFactory]] = {
    "patients": (patients_for_global_search, _patient_item),
    "appointments": (appointments_for_global_search, _appointment_item),
    "payments": (payment_receivables_for_global_search, _payment_item),
    "materials": (materials_for_global_search, _material_item),
}


def global_search_read_model(
    *,
    actor: User,
    query: str,
    requested_types: Iterable[str] | None,
) -> dict[str, Any]:
    allowed = _allowed_categories(actor)
    requested = set(requested_types or GLOBAL_SEARCH_GROUP_TYPES)
    effective_types = [
        category
        for category in GLOBAL_SEARCH_GROUP_TYPES
        if category in allowed and category in requested
    ]
    groups: list[dict[str, Any]] = []
    returned_count = 0
    for category in effective_types:
        selector, item_factory = _CATEGORY_HANDLERS[category]
        rows = list(selector(actor, query)[: GLOBAL_SEARCH_RESULT_LIMIT + 1])
        if not rows:
            continue
        items = [item_factory(row) for row in rows[:GLOBAL_SEARCH_RESULT_LIMIT]]
        groups.append(
            {
                "type": category,
                "has_more": len(rows) > GLOBAL_SEARCH_RESULT_LIMIT,
                "items": items,
            }
        )
        returned_count += len(items)
    return {
        "query": query,
        "groups": groups,
        "returned_count": returned_count,
    }
