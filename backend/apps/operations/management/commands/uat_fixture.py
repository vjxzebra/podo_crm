import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.notifications.models import Notification, NotificationKind, NotificationTone
from apps.patients.models import Patient, PatientMedicalProfile
from apps.scheduling.models import Appointment
from apps.work_items.models import WorkItem, WorkItemKind

UAT_MARKER = "TP-904-UAT"
UAT_RECEPTION_EMAIL = "tp904.reception@podoria.test"
UAT_PODOLOGIST_EMAIL = "tp904.podologist@podoria.test"
UAT_PATIENT_PHONE = "+380000009904"
UAT_ROOM_NAME = "TP-904 UAT кабінет"
UAT_SERVICE_CODE = "UAT904"
KYIV = ZoneInfo("Europe/Kyiv")


def _password_from_env_file(path_value: str, key: str) -> str:
    path = Path(path_value).expanduser().resolve(strict=True)
    matches: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        candidate, value = stripped.split("=", 1)
        if candidate.strip() == key:
            matches.append(value.strip().strip('"').strip("'"))
    if len(matches) != 1 or not matches[0]:
        raise CommandError(f"Credentials file must contain exactly one non-empty {key} entry.")
    return matches[0]


def _cleanup_fixture() -> dict[str, int]:
    users = User.objects.filter(email__in=(UAT_RECEPTION_EMAIL, UAT_PODOLOGIST_EMAIL))
    user_ids = list(users.values_list("pk", flat=True))
    deleted = {
        "notifications": Notification.objects.filter(recipient_id__in=user_ids).delete()[0],
        "work_items": WorkItem.objects.filter(title__startswith=UAT_MARKER).delete()[0],
        "appointments": Appointment.objects.filter(comment=UAT_MARKER).delete()[0],
        "patients": Patient.objects.filter(phone=UAT_PATIENT_PHONE).delete()[0],
        "services": Service.objects.filter(code=UAT_SERVICE_CODE).delete()[0],
        "rooms": Room.objects.filter(name=UAT_ROOM_NAME).delete()[0],
        "users": users.delete()[0],
    }
    return deleted


def _prepare_fixture(password: str) -> dict[str, Any]:
    _cleanup_fixture()
    reception = User.objects.create_user(
        email=UAT_RECEPTION_EMAIL,
        password=password,
        role=UserRole.RECEPTION,
        first_name="Рецепція",
        last_name="TP-904",
    )
    podologist = User.objects.create_user(
        email=UAT_PODOLOGIST_EMAIL,
        password=password,
        role=UserRole.PODOLOGIST,
        first_name="Подолог",
        last_name="TP-904",
    )
    room = Room.objects.create(name=UAT_ROOM_NAME)
    service = Service.objects.create(
        code=UAT_SERVICE_CODE,
        name="TP-904 контрольна послуга",
        duration_minutes=45,
        price_minor=125000,
        color="#2563EB",
    )
    patient = Patient.objects.create(
        first_name="Контрольний",
        last_name="Пацієнт TP-904",
        phone=UAT_PATIENT_PHONE,
        primary_podologist=podologist,
        created_by=reception,
    )
    PatientMedicalProfile.objects.get_or_create(patient=patient)
    local_day = timezone.localdate()
    starts_at = datetime.combine(local_day, time(10, 0), tzinfo=KYIV)
    appointment = Appointment.objects.create(
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
        time_range=(starts_at, starts_at + timedelta(minutes=service.duration_minutes)),
        duration_minutes=service.duration_minutes,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=AppointmentStatusConfig.objects.get(code="CONFIRMED"),
        has_no_complaints=True,
        comment=UAT_MARKER,
    )
    work_item = WorkItem.objects.create(
        kind=WorkItemKind.CONFIRM_APPOINTMENT,
        title=f"{UAT_MARKER}: перевірити запис",
        due_at=starts_at - timedelta(hours=1),
        assignee=podologist,
        patient=patient,
        created_by=reception,
    )
    for recipient in (reception, podologist):
        Notification.objects.create(
            recipient=recipient,
            event_key=f"tp904-uat:{appointment.pk}:{recipient.role}",
            kind=NotificationKind.APPOINTMENT_UPCOMING,
            title="TP-904 контрольне сповіщення",
            message="Read-only UAT fixture",
            tone=NotificationTone.BLUE,
            deep_link="/calendar",
            occurred_at=timezone.now(),
        )
    return {
        "event": "tp904_uat_fixture_prepared",
        "appointment_id": str(appointment.pk),
        "patient_id": str(patient.pk),
        "work_item_id": str(work_item.pk),
        "roles": [UserRole.RECEPTION, UserRole.PODOLOGIST],
        "local_date": local_day.isoformat(),
    }


class Command(BaseCommand):
    help = "Prepare or clean exact local TP-904 UAT fixtures. Refuses to run outside DEBUG."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", choices=("prepare", "cleanup"))
        parser.add_argument("--credentials-file")
        parser.add_argument(
            "--password-key",
            default="PODORIA_LOCAL_ADMIN_PASSWORD",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("uat_fixture is available only when DEBUG is enabled.")
        with transaction.atomic():
            if options["action"] == "prepare":
                if not options["credentials_file"]:
                    raise CommandError("--credentials-file is required for prepare.")
                result = _prepare_fixture(
                    _password_from_env_file(
                        options["credentials_file"],
                        options["password_key"],
                    )
                )
            else:
                result = {
                    "event": "tp904_uat_fixture_cleaned",
                    "deleted": _cleanup_fixture(),
                }
        self.stdout.write(json.dumps(result, sort_keys=True))
