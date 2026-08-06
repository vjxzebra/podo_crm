from datetime import datetime

from django.utils import timezone

from apps.billing.models import (
    PricingState,
    Receivable,
    ReceivableStatus,
    VisitPricing,
)
from apps.clinic.models import AppointmentStatusConfig
from apps.visits.models import Visit, VisitStatus


def complete_visit_with_neutral_pricing(
    visit: Visit,
    *,
    completed_at: datetime | None = None,
    payment_handoff_requested: bool | None = None,
) -> tuple[VisitPricing, Receivable]:
    """Complete a test visit with the canonical no-discount financial aggregate."""
    service_lines = list(visit.service_lines.all())
    if not service_lines:
        raise AssertionError("A completed visit fixture requires at least one service line.")
    gross_minor = sum(line.line_total_minor for line in service_lines)

    pricing_state = PricingState.SETTLED if gross_minor == 0 else PricingState.OPEN
    pricing = VisitPricing.objects.create(
        visit=visit,
        gross_minor=gross_minor,
        discount_amount_minor=0,
        net_minor=gross_minor,
        state=pricing_state,
        settled_at=timezone.now() if pricing_state == PricingState.SETTLED else None,
    )
    receivable = Receivable.objects.create(
        visit=visit,
        amount_minor=gross_minor,
        status=(ReceivableStatus.PAID if gross_minor == 0 else ReceivableStatus.OPEN),
    )

    appointment = visit.appointment
    if appointment.status_id != "COMPLETED":
        appointment.status = AppointmentStatusConfig.objects.get(pk="COMPLETED")
        appointment.save(update_fields=("status", "updated_at"))

    visit.status = VisitStatus.COMPLETED
    visit.total_minor = gross_minor
    visit.completed_at = completed_at or visit.completed_at or timezone.now()
    update_fields = ["status", "total_minor", "completed_at", "updated_at"]
    if payment_handoff_requested is not None:
        visit.payment_handoff_requested = payment_handoff_requested
        update_fields.append("payment_handoff_requested")
    visit.save(update_fields=update_fields)
    return pricing, receivable
