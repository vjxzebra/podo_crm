from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import PasswordResetRequest, User, UserRole
from apps.billing.models import Payment, Receivable, ReceivableStatus, Refund
from apps.clinic.models import ClinicWorkday, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.visits.models import Visit, VisitServiceLine, VisitStatus
from apps.work_items.models import WorkItem
from config.api.exceptions import ApiProblem

CLINIC_TIMEZONE_NAME = "Europe/Kyiv"
CLINIC_TIMEZONE = ZoneInfo(CLINIC_TIMEZONE_NAME)
ACTIVE_OVERVIEW_STATUSES = (
    "NEW",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
)


def _bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(date_from, time.min, tzinfo=CLINIC_TIMEZONE),
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=CLINIC_TIMEZONE),
    )


def _metric(
    key: str,
    label: str,
    value: int,
    value_format: str,
    note: str,
    tone: str,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "format": value_format,
        "note": note,
        "tone": tone,
    }


def _appointment_payload(appointment: Appointment) -> dict[str, object]:
    return {
        "id": appointment.pk,
        "public_number": appointment.public_number,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "duration_minutes": appointment.duration_minutes,
        "patient": {
            "id": appointment.patient_id,
            "public_number": appointment.patient.public_number,
            "display_name": appointment.patient.display_name,
        },
        "specialist": {
            "id": appointment.specialist_id,
            "display_name": appointment.specialist.display_name,
        },
        "service": {
            "id": appointment.service_id,
            "name": appointment.service_name_snapshot,
            "color": appointment.service_color_snapshot,
        },
        "room": {
            "id": appointment.room_id,
            "name": appointment.room_label_snapshot,
        },
        "status": {
            "code": appointment.status_id,
            "label": appointment.status.label,
            "color": appointment.status.color,
        },
    }


def _workday_payload(local_date: date) -> dict[str, Any]:
    workday = (
        ClinicWorkday.objects.prefetch_related("breaks")
        .filter(weekday=local_date.weekday())
        .first()
    )
    if (
        workday is None
        or not workday.is_working
        or workday.start_time is None
        or workday.end_time is None
    ):
        return {
            "is_working": False,
            "starts_at": None,
            "ends_at": None,
            "break_minutes": 0,
            "net_minutes": 0,
        }
    starts_at = datetime.combine(local_date, workday.start_time, tzinfo=CLINIC_TIMEZONE)
    ends_at = datetime.combine(local_date, workday.end_time, tzinfo=CLINIC_TIMEZONE)
    break_minutes = sum(
        int(
            (
                datetime.combine(local_date, item.end_time)
                - datetime.combine(local_date, item.start_time)
            ).total_seconds()
            // 60
        )
        for item in workday.breaks.all()
    )
    total_minutes = int((ends_at - starts_at).total_seconds() // 60)
    return {
        "is_working": True,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "break_minutes": break_minutes,
        "net_minutes": max(0, total_minutes - break_minutes),
    }


def overview_read_model(
    *, actor: User, local_date: date, now: datetime | None = None
) -> dict[str, object]:
    day_start, day_end = _bounds(local_date, local_date)
    appointments = Appointment.objects.select_related(
        "patient", "specialist", "service", "room", "status"
    ).filter(time_range__overlap=(day_start, day_end))
    if actor.role == UserRole.PODOLOGIST:
        appointments = appointments.filter(specialist=actor)
    appointment_list = sorted(
        (item for item in appointments if day_start <= item.starts_at < day_end),
        key=lambda item: (item.starts_at, item.specialist_id, str(item.pk)),
    )
    active = [item for item in appointment_list if item.status_id in ACTIVE_OVERVIEW_STATUSES]
    active_patient_count = len({item.patient_id for item in active})
    workday = _workday_payload(local_date)
    effective_now = now or timezone.now()
    next_threshold = (
        effective_now
        if local_date == effective_now.astimezone(CLINIC_TIMEZONE).date()
        else day_start
    )
    next_item = next((item for item in active if item.starts_at >= next_threshold), None)

    own_attention_count = (
        WorkItem.objects.filter(assignee=actor, is_completed=False)
        .filter(Q(is_important=True) | Q(due_at__lt=effective_now))
        .count()
    )
    attention: list[dict[str, object]] = []

    if actor.role == UserRole.PODOLOGIST:
        metrics = [
            _metric(
                "appointments", "Власні записи", len(active), "integer", "на вибрану дату", "sage"
            ),
            _metric(
                "patients",
                "Власні пацієнти",
                active_patient_count,
                "integer",
                "distinct у розкладі",
                "sand",
            ),
            _metric(
                "workday_minutes",
                "Робочий день",
                int(workday["net_minutes"]),
                "duration",
                "за графіком клініки",
                "lilac",
            ),
            _metric(
                "attention",
                "Потребує уваги",
                own_attention_count,
                "integer",
                "власні справи",
                "coral",
            ),
        ]
        attention.append(
            {
                "kind": "work_items",
                "label": "Власні прострочені або важливі справи",
                "count": own_attention_count,
                "deep_link": "/work-items",
            }
        )
    elif actor.role == UserRole.RECEPTION:
        payments_minor = sum(
            payment.ledger_entry.amount_minor
            for payment in Payment.objects.select_related("ledger_entry").filter(
                ledger_entry__posted_at__gte=day_start,
                ledger_entry__posted_at__lt=day_end,
            )
        )
        refunds_minor = sum(
            refund.ledger_entry.amount_minor
            for refund in Refund.objects.select_related("ledger_entry").filter(
                ledger_entry__posted_at__gte=day_start,
                ledger_entry__posted_at__lt=day_end,
            )
        )
        unpaid = Receivable.objects.filter(status=ReceivableStatus.OPEN).count()
        specialist_count = len({item.specialist_id for item in active})
        metrics = [
            _metric(
                "appointments", "Записи кабінету", len(active), "integer", "без скасованих", "sage"
            ),
            _metric(
                "payments_today_minor",
                "Оплати за день",
                payments_minor - refunds_minor,
                "money",
                "ledger: оплати мінус повернення",
                "sand",
            ),
            _metric(
                "specialists", "Спеціалісти", specialist_count, "integer", "у розкладі", "lilac"
            ),
            _metric(
                "unpaid_visits", "Очікує оплати", unpaid, "integer", "завершені прийоми", "coral"
            ),
        ]
        attention.append(
            {
                "kind": "unpaid_visits",
                "label": "Неоплачені завершені прийоми",
                "count": unpaid,
                "deep_link": "/finance",
            }
        )
    else:
        expected_income = sum(item.service.price_minor for item in active)
        specialist_count = len({item.specialist_id for item in active})
        clinic_work_attention = (
            WorkItem.objects.filter(is_completed=False)
            .filter(Q(is_important=True) | Q(due_at__lt=effective_now))
            .count()
        )
        pending_resets = PasswordResetRequest.objects.filter(resolved_at__isnull=True).count()
        unpaid = Receivable.objects.filter(status=ReceivableStatus.OPEN).count()
        attention_total = clinic_work_attention + pending_resets + unpaid
        metrics = [
            _metric(
                "appointments", "Записи кабінету", len(active), "integer", "без скасованих", "sage"
            ),
            _metric(
                "expected_income_minor",
                "Очікуваний дохід",
                expected_income,
                "money",
                "за цінами каталогу",
                "sand",
            ),
            _metric(
                "specialists", "Спеціалісти", specialist_count, "integer", "у розкладі", "lilac"
            ),
            _metric(
                "attention",
                "Потребує уваги",
                attention_total,
                "integer",
                "справи, доступ і оплати",
                "coral",
            ),
        ]
        attention.extend(
            (
                {
                    "kind": "work_items",
                    "label": "Прострочені або важливі справи",
                    "count": clinic_work_attention,
                    "deep_link": "/work-items",
                },
                {
                    "kind": "password_resets",
                    "label": "Запити відновлення доступу",
                    "count": pending_resets,
                    "deep_link": "/password-resets",
                },
                {
                    "kind": "unpaid_visits",
                    "label": "Неоплачені завершені прийоми",
                    "count": unpaid,
                    "deep_link": "/finance",
                },
            )
        )

    return {
        "role": actor.role,
        "date": local_date,
        "timezone": CLINIC_TIMEZONE_NAME,
        "metrics": metrics,
        "schedule": [_appointment_payload(item) for item in appointment_list],
        "next_appointment": _appointment_payload(next_item) if next_item is not None else None,
        "workday": workday,
        "attention": attention,
    }


def _filter_visits(
    *, start: datetime, end: datetime, specialist_id: int | None, service_id: UUID | None
) -> QuerySet[Visit]:
    queryset = Visit.objects.filter(
        status=VisitStatus.COMPLETED,
        completed_at__gte=start,
        completed_at__lt=end,
    )
    if specialist_id is not None:
        queryset = queryset.filter(specialist_id=specialist_id)
    if service_id is not None:
        queryset = queryset.filter(service_lines__service_id=service_id)
    return queryset.distinct()


def _filter_historical_visits(
    *, end: datetime, patient_ids: set[UUID], specialist_id: int | None, service_id: UUID | None
) -> QuerySet[Visit]:
    queryset = Visit.objects.filter(
        status=VisitStatus.COMPLETED,
        completed_at__lt=end,
        patient_id__in=patient_ids,
    )
    if specialist_id is not None:
        queryset = queryset.filter(specialist_id=specialist_id)
    if service_id is not None:
        queryset = queryset.filter(service_lines__service_id=service_id)
    return queryset.distinct()


def _filter_payments(
    *, start: datetime, end: datetime, specialist_id: int | None, service_id: UUID | None
) -> QuerySet[Payment]:
    queryset = Payment.objects.select_related("ledger_entry", "receivable__visit").filter(
        ledger_entry__posted_at__gte=start,
        ledger_entry__posted_at__lt=end,
    )
    if specialist_id is not None:
        queryset = queryset.filter(receivable__visit__specialist_id=specialist_id)
    if service_id is not None:
        queryset = queryset.filter(receivable__visit__service_lines__service_id=service_id)
    return queryset.distinct()


def _filter_refunds(
    *, start: datetime, end: datetime, specialist_id: int | None, service_id: UUID | None
) -> QuerySet[Refund]:
    queryset = Refund.objects.select_related(
        "ledger_entry", "original_payment__receivable__visit"
    ).filter(
        ledger_entry__posted_at__gte=start,
        ledger_entry__posted_at__lt=end,
    )
    if specialist_id is not None:
        queryset = queryset.filter(original_payment__receivable__visit__specialist_id=specialist_id)
    if service_id is not None:
        queryset = queryset.filter(
            original_payment__receivable__visit__service_lines__service_id=service_id
        )
    return queryset.distinct()


def _filter_appointments(
    *, start: datetime, end: datetime, specialist_id: int | None, service_id: UUID | None
) -> list[Appointment]:
    queryset = Appointment.objects.select_related("specialist", "service", "status").filter(
        time_range__overlap=(start, end)
    )
    if specialist_id is not None:
        queryset = queryset.filter(specialist_id=specialist_id)
    if service_id is not None:
        queryset = queryset.filter(service_id=service_id)
    return [item for item in queryset if start <= item.starts_at < end]


def _round_minor(value: int, divisor: int) -> int:
    if divisor == 0:
        return 0
    return int((Decimal(value) / Decimal(divisor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _rate_bps(numerator: int, denominator: int) -> int:
    return 0 if denominator == 0 else min(10_000, _round_minor(numerator * 10_000, denominator))


def _available_minutes(date_from: date, date_to: date) -> int:
    schedule = {
        item.weekday: item for item in ClinicWorkday.objects.prefetch_related("breaks").all()
    }
    total = 0
    current = date_from
    while current <= date_to:
        workday = schedule.get(current.weekday())
        if (
            workday is not None
            and workday.is_working
            and workday.start_time is not None
            and workday.end_time is not None
        ):
            minutes = int(
                (
                    datetime.combine(current, workday.end_time)
                    - datetime.combine(current, workday.start_time)
                ).total_seconds()
                // 60
            )
            minutes -= sum(
                int(
                    (
                        datetime.combine(current, item.end_time)
                        - datetime.combine(current, item.start_time)
                    ).total_seconds()
                    // 60
                )
                for item in workday.breaks.all()
            )
            total += max(0, minutes)
        current += timedelta(days=1)
    return total


def _trend(
    *,
    date_from: date,
    date_to: date,
    visits: list[Visit],
    payments: list[Payment],
    refunds: list[Refund],
) -> tuple[str, list[dict[str, object]]]:
    days = (date_to - date_from).days + 1
    bucket = "day" if days <= 31 else "week" if days <= 92 else "month"

    def bucket_start(value: date) -> date:
        if bucket == "day":
            return value
        if bucket == "week":
            return date_from + timedelta(days=((value - date_from).days // 7) * 7)
        return value.replace(day=1)

    points: dict[date, dict[str, int]] = {}
    current = date_from
    while current <= date_to:
        key = bucket_start(current)
        points.setdefault(key, {"visits": 0, "revenue_minor": 0})
        current += timedelta(days=1)

    for visit in visits:
        if visit.completed_at is not None:
            points[bucket_start(visit.completed_at.astimezone(CLINIC_TIMEZONE).date())][
                "visits"
            ] += 1
    for payment in payments:
        points[bucket_start(payment.ledger_entry.posted_at.astimezone(CLINIC_TIMEZONE).date())][
            "revenue_minor"
        ] += payment.ledger_entry.amount_minor
    for refund in refunds:
        points[bucket_start(refund.ledger_entry.posted_at.astimezone(CLINIC_TIMEZONE).date())][
            "revenue_minor"
        ] -= refund.ledger_entry.amount_minor

    result = []
    ordered = sorted(points)
    for index, key in enumerate(ordered):
        next_key = ordered[index + 1] if index + 1 < len(ordered) else date_to + timedelta(days=1)
        bucket_end = min(date_to, next_key - timedelta(days=1))
        label = (
            key.strftime("%d.%m")
            if bucket == "day"
            else f"{key.strftime('%d.%m')}–{bucket_end.strftime('%d.%m')}"
            if bucket == "week"
            else key.strftime("%m.%Y")
        )
        result.append({"from": key, "to": bucket_end, "label": label, **points[key]})
    return bucket, result


def analytics_read_model(
    *, date_from: date, date_to: date, specialist_id: int | None, service_id: UUID | None
) -> dict[str, object]:
    start, end = _bounds(date_from, date_to)
    specialists = list(
        User.objects.filter(role=UserRole.PODOLOGIST).order_by(
            "-is_active", "last_name", "first_name", "email", "pk"
        )
    )
    services = list(Service.objects.order_by("-is_active", "name", "code", "pk"))
    selected_specialist = next((item for item in specialists if item.pk == specialist_id), None)
    if specialist_id is not None and selected_specialist is None:
        raise ApiProblem(
            code="not_found",
            message="Спеціаліста не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    selected_service = next((item for item in services if item.pk == service_id), None)
    if service_id is not None and selected_service is None:
        raise ApiProblem(
            code="not_found",
            message="Послугу не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    service_lines = VisitServiceLine.objects.select_related("service")
    visits = list(
        _filter_visits(
            start=start,
            end=end,
            specialist_id=specialist_id,
            service_id=service_id,
        )
        .select_related("patient", "specialist")
        .prefetch_related(Prefetch("service_lines", queryset=service_lines))
        .order_by("completed_at", "id")
    )
    payments = list(
        _filter_payments(start=start, end=end, specialist_id=specialist_id, service_id=service_id)
    )
    refunds = list(
        _filter_refunds(start=start, end=end, specialist_id=specialist_id, service_id=service_id)
    )
    appointments = _filter_appointments(
        start=start, end=end, specialist_id=specialist_id, service_id=service_id
    )

    revenue_minor = sum(item.ledger_entry.amount_minor for item in payments) - sum(
        item.ledger_entry.amount_minor for item in refunds
    )
    served_patient_ids = {visit.patient_id for visit in visits}
    previous_patient_ids = set(
        _filter_historical_visits(
            end=start,
            patient_ids=served_patient_ids,
            specialist_id=specialist_id,
            service_id=service_id,
        ).values_list("patient_id", flat=True)
    )
    new_patient_ids = set(
        Patient.objects.filter(
            pk__in=served_patient_ids,
            created_at__gte=start,
            created_at__lt=end,
        ).values_list("pk", flat=True)
    )

    intervals: list[int] = []
    previous_completion: dict[UUID, datetime] = {}
    history = _filter_historical_visits(
        end=end,
        patient_ids=served_patient_ids,
        specialist_id=specialist_id,
        service_id=service_id,
    ).order_by("patient_id", "completed_at", "id")
    for visit in history:
        completed_at = visit.completed_at
        if completed_at is None:
            continue
        prior = previous_completion.get(visit.patient_id)
        if prior is not None and completed_at >= start:
            intervals.append((completed_at - prior).days)
        previous_completion[visit.patient_id] = completed_at

    outcome_counts: dict[str, int] = defaultdict(int)
    for appointment in appointments:
        outcome_counts[
            appointment.status_id
            if appointment.status_id in {"COMPLETED", "CANCELED", "NO_SHOW"}
            else "OTHER"
        ] += 1

    ranking: dict[UUID, dict[str, Any]] = {}
    for visit in visits:
        for line in visit.service_lines.all():
            if service_id is not None and line.service_id != service_id:
                continue
            item = ranking.setdefault(
                line.service_id,
                {
                    "id": line.service_id,
                    "code": line.service_code,
                    "name": line.service_name,
                    "visit_ids": set(),
                    "quantity": 0,
                    "billed_total_minor": 0,
                },
            )
            item["visit_ids"].add(visit.pk)
            item["quantity"] += line.quantity
            item["billed_total_minor"] += line.line_total_minor
    service_ranking: list[dict[str, Any]] = [
        {
            "id": item["id"],
            "code": item["code"],
            "name": item["name"],
            "visit_count": len(item.pop("visit_ids")),
            "quantity": item["quantity"],
            "billed_total_minor": item["billed_total_minor"],
        }
        for item in ranking.values()
    ]
    service_ranking.sort(
        key=lambda item: (-item["quantity"], -item["billed_total_minor"], item["name"])
    )

    available_minutes = _available_minutes(date_from, date_to)
    specialist_ids_with_activity: set[int] = {
        *(visit.specialist_id for visit in visits),
        *(appointment.specialist_id for appointment in appointments),
        *(payment.receivable.visit.specialist_id for payment in payments),
        *(refund.original_payment.receivable.visit.specialist_id for refund in refunds),
    }
    if specialist_id is not None:
        specialist_ids_with_activity.add(specialist_id)
    visit_counts: dict[int, int] = defaultdict(int)
    scheduled_minutes: dict[int, int] = defaultdict(int)
    specialist_revenue: dict[int, int] = defaultdict(int)
    for visit in visits:
        visit_counts[visit.specialist_id] += 1
    for appointment in appointments:
        if appointment.status_id != "CANCELED":
            scheduled_minutes[appointment.specialist_id] += appointment.duration_minutes
    for payment in payments:
        specialist_revenue[payment.receivable.visit.specialist_id] += (
            payment.ledger_entry.amount_minor
        )
    for refund in refunds:
        specialist_revenue[refund.original_payment.receivable.visit.specialist_id] -= (
            refund.ledger_entry.amount_minor
        )
    performance: list[dict[str, Any]] = [
        {
            "id": specialist.pk,
            "name": specialist.display_name,
            "is_active": specialist.is_active,
            "completed_visits": visit_counts[specialist.pk],
            "scheduled_minutes": scheduled_minutes[specialist.pk],
            "available_minutes": available_minutes,
            "utilization_bps": _rate_bps(scheduled_minutes[specialist.pk], available_minutes),
            "revenue_minor": specialist_revenue[specialist.pk],
        }
        for specialist in specialists
        if specialist.pk in specialist_ids_with_activity
    ]
    performance.sort(
        key=lambda item: (-item["utilization_bps"], -item["completed_visits"], item["name"])
    )

    bucket, trend = _trend(
        date_from=date_from,
        date_to=date_to,
        visits=visits,
        payments=payments,
        refunds=refunds,
    )
    return {
        "period": {
            "from": date_from,
            "to": date_to,
            "timezone": CLINIC_TIMEZONE_NAME,
            "bucket": bucket,
        },
        "filters": {
            "specialist": (
                None
                if selected_specialist is None
                else {
                    "id": str(selected_specialist.pk),
                    "name": selected_specialist.display_name,
                    "is_active": selected_specialist.is_active,
                }
            ),
            "service": (
                None
                if selected_service is None
                else {
                    "id": str(selected_service.pk),
                    "name": selected_service.name,
                    "is_active": selected_service.is_active,
                }
            ),
        },
        "available_specialists": [
            {"id": str(item.pk), "name": item.display_name, "is_active": item.is_active}
            for item in specialists
        ],
        "available_services": [
            {"id": str(item.pk), "name": item.name, "is_active": item.is_active}
            for item in services
        ],
        "kpis": {
            "completed_visits": len(visits),
            "revenue_minor": revenue_minor,
            "payment_count": len(payments),
            "average_check_minor": _round_minor(revenue_minor, len(payments)),
            "returning_patient_rate_bps": _rate_bps(
                len(previous_patient_ids), len(served_patient_ids)
            ),
            "returning_patients": len(previous_patient_ids),
            "served_patients": len(served_patient_ids),
            "new_patients": len(new_patient_ids),
            "canceled_appointments": outcome_counts["CANCELED"],
            "no_show_appointments": outcome_counts["NO_SHOW"],
            "average_return_interval_days": (
                None if not intervals else _round_minor(sum(intervals), len(intervals))
            ),
        },
        "trend": trend,
        "appointment_outcomes": [
            {"code": "COMPLETED", "label": "Завершено", "count": outcome_counts["COMPLETED"]},
            {"code": "CANCELED", "label": "Скасовано", "count": outcome_counts["CANCELED"]},
            {"code": "NO_SHOW", "label": "Неявки", "count": outcome_counts["NO_SHOW"]},
            {"code": "OTHER", "label": "Інші", "count": outcome_counts["OTHER"]},
        ],
        "specialist_performance": performance,
        "service_ranking": service_ranking,
    }
