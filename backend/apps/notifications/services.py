import logging
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.access import route_ids_for
from apps.accounts.models import PasswordResetRequest, User, UserRole
from apps.billing.models import ReceivableStatus
from apps.notifications.models import Notification, NotificationKind, NotificationTone
from apps.scheduling.models import Appointment
from apps.visits.models import Visit, VisitStatus
from apps.work_items.models import WorkItem
from config.api.exceptions import ApiProblem

logger = logging.getLogger("podoria")

DomainNotificationEvent = Literal[
    "appointment_arrived",
    "appointment_canceled",
    "visit_payment_ready",
    "password_reset_requested",
]

_ROUTE_ID_BY_ROOT = {
    "calendar": "calendar",
    "patients": "patients",
    "finance": "finance",
    "inventory": "inventory",
    "work-items": "work-items",
    "password-resets": "password-resets",
    "notifications": "notifications",
    "audit": "audit",
}


def safe_notification_deep_link(*, recipient: User, value: str) -> str:
    candidate = value.strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
        or len(candidate) > 500
    ):
        return "/"
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return "/"
    if parsed.path == "/":
        return "/"
    root = parsed.path.lstrip("/").split("/", 1)[0]
    route_id = _ROUTE_ID_BY_ROOT.get(root)
    if route_id is None or route_id not in route_ids_for(recipient):
        return "/"
    return candidate


def create_notification(
    *,
    recipient: User,
    event_key: str,
    kind: str,
    title: str,
    message: str,
    deep_link: str,
    occurred_at: datetime | None = None,
    tone: str = NotificationTone.SAGE,
    is_important: bool = False,
) -> tuple[Notification | None, bool]:
    if not recipient.is_active:
        return None, False
    normalized_event_key = event_key.strip()
    normalized_title = title.strip()
    normalized_message = message.strip()
    if not normalized_event_key or len(normalized_event_key) > 255:
        raise ValueError("Notification event_key must contain at most 255 characters.")
    if not normalized_title or not normalized_message:
        raise ValueError("Notification title and message are required.")
    if kind not in NotificationKind.values:
        raise ValueError("Unknown notification kind.")
    if tone not in NotificationTone.values:
        raise ValueError("Unknown notification tone.")
    notification, created = Notification.objects.get_or_create(
        recipient=recipient,
        event_key=normalized_event_key,
        defaults={
            "kind": kind,
            "title": normalized_title,
            "message": normalized_message,
            "deep_link": safe_notification_deep_link(recipient=recipient, value=deep_link),
            "occurred_at": occurred_at or timezone.now(),
            "tone": tone,
            "is_important": is_important,
        },
    )
    if created:
        from apps.notifications.telegram_services import (
            enqueue_notification_telegram_delivery_on_commit,
        )

        enqueue_notification_telegram_delivery_on_commit(notification)
    return notification, created


@transaction.atomic
def mark_notification_read(*, actor: User, notification_id: UUID) -> Notification:
    notification = (
        Notification.objects.select_for_update().filter(recipient=actor, pk=notification_id).first()
    )
    if notification is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at",))
    return notification


@transaction.atomic
def mark_all_notifications_read(*, actor: User) -> int:
    return Notification.objects.filter(recipient=actor, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def _appointment_time(appointment: Appointment) -> str:
    local_start = timezone.localtime(appointment.starts_at)
    return local_start.strftime("%d.%m.%Y, %H:%M")


def _money(amount_minor: int) -> str:
    whole, fraction = divmod(amount_minor, 100)
    return f"{whole:,}".replace(",", " ") + f",{fraction:02d} грн"


def _dispatch_appointment_event(
    *,
    event: DomainNotificationEvent,
    object_id: str,
    event_version: int | None,
    actor_id: int | None,
) -> int:
    try:
        appointment_id = UUID(object_id)
    except ValueError:
        return 0
    appointment = (
        Appointment.objects.select_related("patient", "specialist")
        .filter(pk=appointment_id)
        .first()
    )
    if appointment is None or (event_version is not None and appointment.version != event_version):
        return 0
    expected_status = "ARRIVED" if event == "appointment_arrived" else "CANCELED"
    if appointment.status_id != expected_status:
        return 0
    recipient = appointment.specialist
    if not recipient.is_active:
        return 0
    if event == "appointment_arrived":
        title = "Пацієнт уже прибув"
        message = (
            f"{appointment.patient.display_name} очікує на прийом "
            f"о {_appointment_time(appointment)}."
        )
        tone = NotificationTone.SAGE
        important = True
    else:
        title = "Запис скасовано"
        message = (
            f"{appointment.patient.display_name} · {appointment.service_name_snapshot} · "
            f"{_appointment_time(appointment)}."
        )
        tone = NotificationTone.CORAL
        important = True
    _, created = create_notification(
        recipient=recipient,
        event_key=f"appointment:{appointment.pk}:status:{expected_status}:v{appointment.version}",
        kind=event,
        title=title,
        message=message,
        deep_link=f"/calendar?appointment={appointment.pk}",
        occurred_at=appointment.updated_at,
        tone=tone,
        is_important=important,
    )
    return int(created)


def _dispatch_visit_payment_ready(*, object_id: str, event_version: int | None) -> int:
    try:
        visit_id = UUID(object_id)
    except ValueError:
        return 0
    visit = (
        Visit.objects.select_related("patient", "appointment", "receivable")
        .filter(
            pk=visit_id,
            status=VisitStatus.COMPLETED,
            payment_handoff_requested=True,
            receivable__status=ReceivableStatus.OPEN,
            receivable__amount_minor__gt=0,
        )
        .first()
    )
    if visit is None or (event_version is not None and visit.version != event_version):
        return 0
    created_count = 0
    recipients = User.objects.filter(
        is_active=True,
        role__in=(UserRole.RECEPTION, UserRole.ADMIN),
    )
    for recipient in recipients.iterator():
        _, created = create_notification(
            recipient=recipient,
            event_key=f"visit:{visit.pk}:payment-ready:{visit.receivable.pk}",
            kind=NotificationKind.VISIT_PAYMENT_READY,
            title="Прийом очікує оплати",
            message=(
                f"{visit.patient.display_name} · {visit.appointment.service_name_snapshot} · "
                f"{_money(visit.receivable.amount_minor)}."
            ),
            deep_link=f"/finance?operation=PAYMENT:{visit.receivable.pk}",
            occurred_at=visit.completed_at,
            tone=NotificationTone.SAND,
            is_important=True,
        )
        created_count += int(created)
    return created_count


def _dispatch_password_reset_requested(*, object_id: str) -> int:
    try:
        request_id = int(object_id)
    except ValueError:
        return 0
    reset_request = (
        PasswordResetRequest.objects.select_related("user")
        .filter(pk=request_id, resolved_at__isnull=True)
        .first()
    )
    if reset_request is None:
        return 0
    created_count = 0
    for recipient in User.objects.filter(is_active=True, role=UserRole.ADMIN).iterator():
        _, created = create_notification(
            recipient=recipient,
            event_key=f"password-reset:{reset_request.pk}:requested",
            kind=NotificationKind.PASSWORD_RESET_REQUESTED,
            title="Запит на скидання пароля",
            message=f"{reset_request.user.display_name} не може увійти до CRM.",
            deep_link="/password-resets",
            occurred_at=reset_request.requested_at,
            tone=NotificationTone.CORAL,
            is_important=True,
        )
        created_count += int(created)
    return created_count


def dispatch_domain_notification_event(
    *,
    event: DomainNotificationEvent,
    object_id: str,
    event_version: int | None = None,
    actor_id: int | None = None,
) -> int:
    if event in ("appointment_arrived", "appointment_canceled"):
        return _dispatch_appointment_event(
            event=event,
            object_id=object_id,
            event_version=event_version,
            actor_id=actor_id,
        )
    if event == "visit_payment_ready":
        return _dispatch_visit_payment_ready(object_id=object_id, event_version=event_version)
    if event == "password_reset_requested":
        return _dispatch_password_reset_requested(object_id=object_id)
    return 0


def notify_domain_event_on_commit(
    *,
    event: DomainNotificationEvent,
    object_id: str,
    event_version: int | None = None,
    actor_id: int | None = None,
) -> None:
    def dispatch_safely() -> None:
        try:
            dispatch_domain_notification_event(
                event=event,
                object_id=object_id,
                event_version=event_version,
                actor_id=actor_id,
            )
        except Exception:
            logger.exception(
                "notification_dispatch_failed",
                extra={"event": event, "object_id": object_id},
            )

    transaction.on_commit(dispatch_safely)


def dispatch_due_reminders(*, now: datetime | None = None) -> int:
    current_time = now or timezone.now()
    created_count = 0
    reminder_start = current_time + timedelta(minutes=14)
    reminder_end = current_time + timedelta(minutes=16)
    appointments = Appointment.objects.select_related("patient", "specialist").filter(
        specialist__is_active=True,
        specialist__role=UserRole.PODOLOGIST,
        status_id__in=("NEW", "AWAITING_CONFIRMATION", "CONFIRMED"),
        time_range__startswith__gte=reminder_start,
        time_range__startswith__lt=reminder_end,
    )
    for appointment in appointments.iterator():
        _, created = create_notification(
            recipient=appointment.specialist,
            event_key=f"appointment:{appointment.pk}:upcoming:{appointment.starts_at.isoformat()}",
            kind=NotificationKind.APPOINTMENT_UPCOMING,
            title="Наступний прийом через 15 хв",
            message=(
                f"{appointment.patient.display_name} · {appointment.service_name_snapshot} · "
                f"{_appointment_time(appointment)}."
            ),
            deep_link=f"/calendar?appointment={appointment.pk}",
            occurred_at=current_time,
            tone=NotificationTone.BLUE,
        )
        created_count += int(created)

    work_items = WorkItem.objects.select_related("assignee", "patient").filter(
        assignee__is_active=True,
        is_completed=False,
        due_at__lte=current_time,
    )
    for work_item in work_items.iterator():
        patient = f" · {work_item.patient.display_name}" if work_item.patient is not None else ""
        _, created = create_notification(
            recipient=work_item.assignee,
            event_key=f"work-item:{work_item.pk}:overdue:{work_item.due_at.isoformat()}",
            kind=NotificationKind.WORK_ITEM_OVERDUE,
            title="Справу прострочено",
            message=f"{work_item.title}{patient}.",
            deep_link=f"/work-items?item={work_item.pk}",
            occurred_at=work_item.due_at,
            tone=NotificationTone.CORAL,
            is_important=work_item.is_important,
        )
        created_count += int(created)
    return created_count
