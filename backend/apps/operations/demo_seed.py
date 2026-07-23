from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.billing.models import (
    CashLedgerEntry,
    CashShift,
    Payment,
    PaymentMethod,
    Receivable,
    Refund,
)
from apps.billing.services import (
    available_cash_minor,
    close_cash_shift,
    open_cash_shift,
    post_cash_movement,
    post_payment,
    post_refund,
)
from apps.clinic.models import (
    AppointmentStatusConfig,
    ClinicBreak,
    ClinicWorkday,
    Room,
    Service,
)
from apps.clinic.services import get_clinic_profile
from apps.inventory.models import (
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
    Supplier,
)
from apps.inventory.services import (
    create_stocktake,
    post_manual_writeoff,
    post_receipt,
    post_stocktake,
)
from apps.notifications.models import Notification, NotificationKind, NotificationTone
from apps.patients.models import Patient, PatientMedicalProfile
from apps.scheduling.models import Appointment
from apps.visits.finish_services import finish_visit
from apps.visits.models import (
    DetectedCondition,
    Visit,
    VisitPhoto,
    VisitPhotoKind,
    VisitPhotoPreviewStatus,
)
from apps.visits.services import save_visit_draft, start_visit
from apps.work_items.models import WorkItem, WorkItemKind
from config.object_storage import delete_private_object, put_private_object

DEMO_SEED_VERSION = "2026-07-23-v1"
DEMO_CONFIRMATION = "SEED_PODORIA_DEMO_DATA"
DEMO_CORE_MARKER = f"demo-seed:{DEMO_SEED_VERSION}:phase:core"
DEMO_PAYMENTS_MARKER = f"demo-seed:{DEMO_SEED_VERSION}:phase:payments"
DEMO_COMPLETE_MARKER = f"demo-seed:{DEMO_SEED_VERSION}:phase:complete"
KYIV = ZoneInfo("Europe/Kyiv")


@dataclass(frozen=True)
class DemoScale:
    patients: int
    appointments: int
    materials: int
    suppliers: int
    services: int
    rooms: int
    work_items: int
    photo_visits: int
    podologists: int
    receptionists: int


DEMO_SCALES = {
    "small": DemoScale(
        patients=12,
        appointments=28,
        materials=8,
        suppliers=3,
        services=6,
        rooms=2,
        work_items=16,
        photo_visits=2,
        podologists=2,
        receptionists=1,
    ),
    "large": DemoScale(
        patients=140,
        appointments=360,
        materials=36,
        suppliers=10,
        services=12,
        rooms=4,
        work_items=90,
        photo_visits=20,
        podologists=4,
        receptionists=3,
    ),
}

FIRST_NAMES = (
    "Олена",
    "Наталія",
    "Ірина",
    "Марія",
    "Тетяна",
    "Оксана",
    "Анна",
    "Катерина",
    "Світлана",
    "Людмила",
    "Андрій",
    "Олександр",
    "Максим",
    "Віктор",
    "Роман",
    "Дмитро",
    "Ігор",
    "Тарас",
)
LAST_NAMES = (
    "Коваль",
    "Бондаренко",
    "Мельник",
    "Шевченко",
    "Кравчук",
    "Поліщук",
    "Ткаченко",
    "Олійник",
    "Петренко",
    "Савчук",
    "Марченко",
    "Лисенко",
    "Романюк",
    "Гнатюк",
    "Бойко",
    "Мазур",
)
SERVICE_SPECS = (
    ("CONSULT", "Консультація подолога", 30, 55000, "#2563EB"),
    ("PEDI-MED", "Медичний педикюр", 75, 145000, "#7C3AED"),
    ("NAIL-CORR", "Корекція нігтьової пластини", 60, 125000, "#0F766E"),
    ("CORN", "Обробка мозоля", 45, 85000, "#EA580C"),
    ("FISSURE", "Обробка тріщин", 60, 110000, "#DC2626"),
    ("ONYCHO", "Комплекс при оніхомікозі", 75, 160000, "#9333EA"),
    ("INGROWN", "Обробка врослого нігтя", 60, 135000, "#0891B2"),
    ("ORTHONYX", "Встановлення корекційної системи", 90, 220000, "#4F46E5"),
    ("CONTROL", "Контрольний огляд", 30, 45000, "#16A34A"),
    ("DIABETIC", "Догляд за діабетичною стопою", 75, 175000, "#BE123C"),
    ("WART", "Обробка підошовної бородавки", 45, 95000, "#CA8A04"),
    ("HOME-CARE", "Підбір домашнього догляду", 30, 35000, "#64748B"),
)
STATUS_CONFIG_SPECS = (
    ("NEW", "Новий", "#64748B", True, True, False),
    ("PENDING_CONFIRMATION", "Очікує підтвердження", "#F59E0B", True, True, False),
    ("CONFIRMED", "Підтверджено", "#2563EB", True, True, False),
    ("ARRIVED", "Пацієнт прийшов", "#7C3AED", True, True, True),
    ("IN_PROGRESS", "Прийом триває", "#0F766E", True, False, True),
    ("COMPLETED", "Завершено", "#16A34A", True, False, True),
    ("CANCELED", "Скасовано", "#DC2626", True, True, False),
    ("NO_SHOW", "Неявка", "#475569", True, True, False),
)
MATERIAL_NAMES = (
    ("Антисептик для шкіри", "Антисептики", "мл"),
    ("Одноразове лезо №10", "Інструменти", "шт"),
    ("Абразивний ковпачок 10 мм", "Абразиви", "шт"),
    ("Фреза алмазна конусна", "Фрези", "шт"),
    ("Тампонувальний матеріал", "Перев'язувальні", "см"),
    ("Крем із сечовиною 30%", "Домашній догляд", "мл"),
    ("Спрей протигрибковий", "Домашній догляд", "мл"),
    ("Корекційна нитка", "Ортоніксія", "см"),
    ("Клей медичний", "Ортоніксія", "мл"),
    ("Серветки безворсові", "Витратні матеріали", "шт"),
    ("Рукавички нітрилові", "Захист", "пар"),
    ("Маска медична", "Захист", "шт"),
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _correlation(section: str, index: int | None = None) -> str:
    suffix = "" if index is None else f":{index:04d}"
    return f"demo-seed:{DEMO_SEED_VERSION}:{section}{suffix}"


def _current_counts() -> dict[str, int]:
    return {
        "users": User.objects.count(),
        "patients": Patient.objects.count(),
        "medical_profiles": PatientMedicalProfile.objects.count(),
        "rooms": Room.objects.count(),
        "services": Service.objects.count(),
        "appointments": Appointment.objects.count(),
        "visits": Visit.objects.count(),
        "visit_photos": VisitPhoto.objects.count(),
        "suppliers": Supplier.objects.count(),
        "materials": Material.objects.count(),
        "material_lots": MaterialLot.objects.count(),
        "inventory_operations": InventoryOperation.objects.count(),
        "stock_movements": StockMovement.objects.count(),
        "stocktakes": Stocktake.objects.count(),
        "receivables": Receivable.objects.count(),
        "payments": Payment.objects.count(),
        "refunds": Refund.objects.count(),
        "cash_shifts": CashShift.objects.count(),
        "cash_ledger_entries": CashLedgerEntry.objects.count(),
        "work_items": WorkItem.objects.count(),
        "notifications": Notification.objects.count(),
        "audit_events": AuditEvent.objects.count(),
    }


def _phase_marker(correlation_id: str) -> AuditEvent | None:
    return AuditEvent.objects.filter(correlation_id=correlation_id).first()


def _validate_marker_scale(marker: AuditEvent | None, *, scale_name: str) -> None:
    if marker is not None and marker.after.get("scale") != scale_name:
        raise ValueError(
            "Demo marker exists with another scale. Reset the CRM database before seeding."
        )


def _preflight(*, scale_name: str) -> tuple[User, str]:
    complete_marker = _phase_marker(DEMO_COMPLETE_MARKER)
    payments_marker = _phase_marker(DEMO_PAYMENTS_MARKER)
    core_marker = _phase_marker(DEMO_CORE_MARKER)
    for marker in (complete_marker, payments_marker, core_marker):
        _validate_marker_scale(marker, scale_name=scale_name)
    if complete_marker is not None:
        admin = User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        if admin is None:
            raise ValueError("An active initial administrator is required.")
        return admin, "complete"
    if payments_marker is not None:
        admin = User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        if admin is None:
            raise ValueError("An active initial administrator is required.")
        return admin, "payments"
    if core_marker is not None:
        admin = User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        if admin is None:
            raise ValueError("An active initial administrator is required.")
        return admin, "core"

    occupied = {
        "non_superusers": User.objects.exclude(is_superuser=True).count(),
        "patients": Patient.objects.count(),
        "services": Service.objects.count(),
        "appointments": Appointment.objects.count(),
        "visits": Visit.objects.count(),
        "suppliers": Supplier.objects.count(),
        "materials": Material.objects.count(),
        "inventory_operations": InventoryOperation.objects.count(),
        "cash_shifts": CashShift.objects.count(),
        "work_items": WorkItem.objects.count(),
        "notifications": Notification.objects.count(),
    }
    conflicts = {key: value for key, value in occupied.items() if value}
    if conflicts:
        details = ", ".join(f"{key}={value}" for key, value in sorted(conflicts.items()))
        raise ValueError(
            "Demo data can be seeded only into an empty CRM domain database. "
            f"Found: {details}. Use the guarded production reset first."
        )

    admin = User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
    if admin is None:
        raise ValueError("Create the initial production administrator before demo seeding.")
    return admin, "empty"


def _create_users(
    *,
    admin: User,
    scale: DemoScale,
) -> tuple[list[User], list[User], User]:
    podologists: list[User] = []
    receptionists: list[User] = []
    for index in range(1, scale.podologists + 1):
        user = User.objects.create_user(
            email=f"demo.podologist.{index:02d}@podoria.test",
            password=None,
            role=UserRole.PODOLOGIST,
            first_name=FIRST_NAMES[index + 1],
            last_name=f"Подолог {index:02d}",
            phone=f"+380670100{index:03d}",
            is_active=index != scale.podologists,
        )
        podologists.append(user)
    for index in range(1, scale.receptionists + 1):
        user = User.objects.create_user(
            email=f"demo.reception.{index:02d}@podoria.test",
            password=None,
            role=UserRole.RECEPTION,
            first_name=FIRST_NAMES[index + 6],
            last_name=f"Рецепція {index:02d}",
            phone=f"+380670200{index:03d}",
        )
        receptionists.append(user)
    demo_admin = User.objects.create_user(
        email="demo.admin.01@podoria.test",
        password=None,
        role=UserRole.ADMIN,
        first_name="Демо",
        last_name="Адміністратор",
        phone="+380670300001",
        is_staff=True,
    )
    for index, user in enumerate([*podologists, *receptionists, demo_admin], start=1):
        record_audit_event(
            actor=admin,
            action=AuditAction.USER_CREATED,
            object_type="user",
            object_id=user.pk,
            object_label=user.display_name,
            correlation_id=_correlation("users", index),
            after={"email": user.email, "role": user.role, "is_active": user.is_active},
            description="Створено демонстраційного працівника.",
        )
    return podologists, receptionists, demo_admin


def _configure_clinic(
    *,
    admin: User,
    scale: DemoScale,
) -> tuple[list[Room], list[Service]]:
    profile = get_clinic_profile()
    for (
        code,
        label,
        color,
        manual_admin,
        manual_reception,
        manual_podologist,
    ) in STATUS_CONFIG_SPECS:
        AppointmentStatusConfig.objects.get_or_create(
            code=code,
            defaults={
                "label": label,
                "color": color,
                "manual_admin": manual_admin,
                "manual_reception": manual_reception,
                "manual_podologist": manual_podologist,
            },
        )
    for weekday in range(7):
        is_working = weekday < 5
        workday, created = ClinicWorkday.objects.get_or_create(
            weekday=weekday,
            defaults={
                "is_working": is_working,
                "start_time": time(9, 0) if is_working else None,
                "end_time": time(18, 0) if is_working else None,
            },
        )
        if created and is_working:
            ClinicBreak.objects.create(
                workday=workday,
                start_time=time(13, 0),
                end_time=time(14, 0),
            )
    before = {
        "name": profile.name,
        "phone": profile.phone,
        "email": profile.email,
        "address": profile.address,
    }
    profile.name = "Podoria — демонстраційна клініка"
    profile.phone = "+380 67 555 01 01"
    profile.email = "clinic-demo@podoria.test"
    profile.address = "м. Хмельницький, вул. Демонстраційна, 12"
    profile.description = "Великий синтетичний набір даних для перевірки всіх розділів CRM."
    profile.version += 1
    profile.save()
    record_audit_event(
        actor=admin,
        action=AuditAction.CLINIC_PROFILE_UPDATED,
        object_type="clinic_profile",
        object_id=profile.pk,
        object_label=profile.name,
        correlation_id=_correlation("clinic"),
        before=before,
        after={"name": profile.name, "phone": profile.phone, "email": profile.email},
        description="Налаштовано демонстраційний профіль клініки.",
    )

    rooms = list(Room.objects.order_by("created_at", "pk")[:1])
    if rooms:
        rooms[0].name = "Кабінет 1 · Основний"
        rooms[0].save(update_fields=("name", "updated_at"))
    while len(rooms) < scale.rooms:
        room = Room.objects.create(name=f"Кабінет {len(rooms) + 1} · Demo")
        rooms.append(room)
        record_audit_event(
            actor=admin,
            action=AuditAction.ROOM_CREATED,
            object_type="room",
            object_id=room.pk,
            object_label=room.name,
            correlation_id=_correlation("rooms", len(rooms)),
            after={"name": room.name, "is_active": room.is_active},
            description="Створено демонстраційний кабінет.",
        )

    services: list[Service] = []
    for index, (code, name, duration, price, color) in enumerate(
        SERVICE_SPECS[: scale.services],
        start=1,
    ):
        service = Service.objects.create(
            code=f"DEMO-{code}",
            name=name,
            duration_minutes=duration,
            price_minor=price,
            color=color,
            is_active=index != scale.services,
        )
        services.append(service)
        record_audit_event(
            actor=admin,
            action=AuditAction.SERVICE_CREATED,
            object_type="service",
            object_id=service.pk,
            object_label=service.name,
            correlation_id=_correlation("services", index),
            after={
                "code": service.code,
                "name": service.name,
                "price_minor": service.price_minor,
                "is_active": service.is_active,
            },
            description="Створено демонстраційну послугу.",
        )
    return rooms, services


def _create_patients(
    *,
    admin: User,
    podologists: list[User],
    count: int,
) -> list[Patient]:
    active_podologists = [user for user in podologists if user.is_active]
    patients: list[Patient] = []
    today = timezone.localdate()
    for index in range(1, count + 1):
        patient = Patient.objects.create(
            first_name=FIRST_NAMES[(index - 1) % len(FIRST_NAMES)],
            last_name=LAST_NAMES[((index - 1) * 3) % len(LAST_NAMES)],
            phone=f"+3807300{index:05d}",
            email=f"demo.patient.{index:04d}@example.test" if index % 3 == 0 else "",
            birth_date=today - timedelta(days=365 * (24 + index % 52) + (index * 17) % 365),
            note=(
                "Демонстраційна картка: бажаний час після 15:00."
                if index % 5 == 0
                else "Демонстраційна картка для перевірки пошуку та історії."
            ),
            primary_podologist=active_podologists[index % len(active_podologists)],
            created_by=admin,
        )
        Patient.objects.filter(pk=patient.pk).update(
            created_at=timezone.now() - timedelta(days=index % 180)
        )
        PatientMedicalProfile.objects.create(
            patient=patient,
            allergies=["латекс"] if index % 11 == 0 else [],
            chronic_conditions=(
                ["цукровий діабет II тип"]
                if index % 13 == 0
                else (["варикозна хвороба"] if index % 9 == 0 else [])
            ),
            notes=(
                "Потребує делікатної обробки та контролю стану шкіри."
                if index % 7 == 0
                else "Регулярний профілактичний догляд."
            ),
        )
        patients.append(patient)
        record_audit_event(
            actor=admin,
            action=AuditAction.PATIENT_CREATED,
            object_type="patient",
            object_id=patient.pk,
            object_label=patient.display_name,
            correlation_id=_correlation("patients", index),
            after={
                "public_number": patient.public_number,
                "name": patient.display_name,
                "primary_podologist_id": patient.primary_podologist_id,
            },
            description="Створено демонстраційну картку пацієнта.",
        )
    return patients


def _create_inventory(
    *,
    admin: User,
    scale: DemoScale,
) -> tuple[list[Supplier], list[Material], list[MaterialLot]]:
    suppliers: list[Supplier] = []
    for index in range(1, scale.suppliers + 1):
        supplier = Supplier.objects.create(
            name=f"Demo Постачальник {index:02d}",
            contact_name=f"Менеджер {FIRST_NAMES[index % len(FIRST_NAMES)]}",
            phone=f"+380680400{index:03d}",
            email=f"supplier.{index:02d}@podoria.test",
            address=f"Складська вулиця, {index}",
            note="Синтетичний постачальник для тестування довідника.",
            is_active=index != scale.suppliers,
        )
        suppliers.append(supplier)
        record_audit_event(
            actor=admin,
            action=AuditAction.SUPPLIER_CREATED,
            object_type="supplier",
            object_id=supplier.pk,
            object_label=supplier.name,
            correlation_id=_correlation("suppliers", index),
            after={"name": supplier.name, "is_active": supplier.is_active},
            description="Створено демонстраційного постачальника.",
        )

    materials: list[Material] = []
    for index in range(1, scale.materials + 1):
        base_name, category, unit = MATERIAL_NAMES[(index - 1) % len(MATERIAL_NAMES)]
        material = Material.objects.create(
            sku=f"DEMO-MAT-{index:03d}",
            name=f"{base_name} · {index:02d}",
            category=category,
            unit=unit,
            minimum_quantity=Decimal(str(5 + index % 7)),
            is_active=index != scale.materials,
        )
        materials.append(material)
        record_audit_event(
            actor=admin,
            action=AuditAction.MATERIAL_CREATED,
            object_type="material",
            object_id=material.pk,
            object_label=material.name,
            correlation_id=_correlation("materials", index),
            after={
                "sku": material.sku,
                "name": material.name,
                "unit": material.unit,
                "is_active": material.is_active,
            },
            description="Створено демонстраційний матеріал.",
        )

    today = timezone.localdate()
    active_materials = [material for material in materials if material.is_active]
    receipt_lines: list[dict[str, Any]] = []
    operation_index = 1
    for index, material in enumerate(active_materials, start=1):
        supplier = suppliers[(index - 1) % max(1, len(suppliers) - 1)]
        lot_count = 1 if index % 5 in {0, 1} else 2
        for lot_index in range(1, lot_count + 1):
            if lot_index == 1 and index % 7 == 0:
                expires_on: date | None = today - timedelta(days=10)
            elif lot_index == 1 and index % 6 == 0:
                expires_on = today + timedelta(days=35)
            else:
                expires_on = today + timedelta(days=180 + 90 * lot_index + index)
            receipt_lines.append(
                {
                    "material_id": material.pk,
                    "lot_number": f"DM-{index:03d}-{lot_index:02d}",
                    "expires_on": expires_on,
                    "quantity": Decimal(str(20 + index + lot_index * 5)),
                    "purchase_price_minor": 1200 + index * 135,
                    "supplier_id": supplier.pk,
                    "supplier_name": "",
                    "allow_existing_lot": False,
                }
            )
            if len(receipt_lines) == 8:
                post_receipt(
                    actor=admin,
                    correlation_id=_correlation("receipts", operation_index),
                    idempotency_key=f"demo-receipt-{DEMO_SEED_VERSION}-{operation_index:03d}",
                    data={
                        "received_on": today - timedelta(days=30 + operation_index),
                        "comment": "Початкове демонстраційне надходження.",
                        "lines": receipt_lines,
                    },
                )
                receipt_lines = []
                operation_index += 1
    if receipt_lines:
        post_receipt(
            actor=admin,
            correlation_id=_correlation("receipts", operation_index),
            idempotency_key=f"demo-receipt-{DEMO_SEED_VERSION}-{operation_index:03d}",
            data={
                "received_on": today - timedelta(days=30 + operation_index),
                "comment": "Початкове демонстраційне надходження.",
                "lines": receipt_lines,
            },
        )

    lots = list(MaterialLot.objects.select_related("material").order_by("material__sku", "pk"))
    writeoff_lines: list[dict[str, Any]] = []
    for index, material in enumerate(active_materials, start=1):
        material_lots = [lot for lot in lots if lot.material_id == material.pk]
        if not material_lots or index % 5 not in {0, 1}:
            continue
        lot = material_lots[0]
        target = Decimal("0") if index % 5 == 0 else Decimal("2")
        quantity = lot.current_quantity - target
        if quantity > 0:
            writeoff_lines.append({"lot_id": lot.pk, "quantity": quantity})
    if writeoff_lines:
        post_manual_writeoff(
            actor=admin,
            correlation_id=_correlation("writeoff"),
            idempotency_key=f"demo-writeoff-{DEMO_SEED_VERSION}",
            data={
                "reason": "Демонстраційне списання",
                "comment": "Формує низькі та нульові залишки для UI.",
                "lines": writeoff_lines,
            },
        )

    usable_lots = list(
        MaterialLot.objects.select_related("material")
        .filter(current_quantity__gt=0, material__is_active=True)
        .order_by("material__sku", "pk")[: min(10, scale.materials)]
    )
    if usable_lots:
        stocktake, _ = create_stocktake(
            actor=admin,
            correlation_id=_correlation("stocktake"),
            idempotency_key=f"demo-stocktake-{DEMO_SEED_VERSION}",
            data={
                "comment": "Контрольна демонстраційна інвентаризація.",
                "lines": [
                    {
                        "lot_id": lot.pk,
                        "actual_quantity": lot.current_quantity
                        + (Decimal("1") if index % 2 == 0 else Decimal("-0.5")),
                    }
                    for index, lot in enumerate(usable_lots)
                    if lot.current_quantity >= Decimal("0.5")
                ],
            },
        )
        post_stocktake(
            actor=admin,
            stocktake_id=stocktake.pk,
            correlation_id=_correlation("stocktake-post"),
            idempotency_key=f"demo-stocktake-post-{DEMO_SEED_VERSION}",
        )
    return (
        suppliers,
        materials,
        list(MaterialLot.objects.select_related("material").order_by("material__sku", "pk")),
    )


def _appointment_status(day_offset: int, slot: int, index: int) -> str:
    if day_offset < -10:
        return ("COMPLETED", "COMPLETED", "COMPLETED", "NO_SHOW", "CANCELED")[index % 5]
    if day_offset < 0:
        return ("COMPLETED", "ARRIVED", "IN_PROGRESS", "CONFIRMED")[index % 4]
    if day_offset == 0:
        return ("ARRIVED", "CONFIRMED")[slot]
    return ("NEW", "PENDING_CONFIRMATION", "CONFIRMED", "CANCELED")[index % 4]


def _create_appointments_and_visits(
    *,
    admin: User,
    scale: DemoScale,
    podologists: list[User],
    rooms: list[Room],
    services: list[Service],
    patients: list[Patient],
    lots: list[MaterialLot],
) -> tuple[list[Appointment], list[Visit]]:
    active_podologists = [user for user in podologists if user.is_active]
    active_services = [service for service in services if service.is_active]
    usable_lots = [
        lot
        for lot in lots
        if lot.current_quantity > Decimal("3") and not lot.is_expired and lot.material.is_active
    ]
    statuses = AppointmentStatusConfig.objects.in_bulk()
    today = timezone.localdate()
    first_day_offset = -(scale.appointments // 3)
    appointments: list[Appointment] = []
    visits: list[Visit] = []

    for index in range(scale.appointments):
        slot = index % 2
        day_offset = first_day_offset + index // 2
        local_start = datetime.combine(
            today + timedelta(days=day_offset),
            time(9, 30) if slot == 0 else time(15, 30),
            tzinfo=KYIV,
        )
        specialist = active_podologists[(index + day_offset) % len(active_podologists)]
        room = rooms[(index + slot) % len(rooms)]
        service = active_services[index % len(active_services)]
        patient = patients[(index * 7) % len(patients)]
        status_code = _appointment_status(day_offset, slot, index)
        initial_status = "ARRIVED" if status_code in {"COMPLETED", "IN_PROGRESS"} else status_code
        appointment = Appointment.objects.create(
            patient=patient,
            specialist=specialist,
            service=service,
            room=room,
            time_range=(
                local_start,
                local_start + timedelta(minutes=service.duration_minutes),
            ),
            duration_minutes=service.duration_minutes,
            service_name_snapshot=service.name,
            service_color_snapshot=service.color,
            room_label_snapshot=room.name,
            status=statuses[initial_status],
            complaints=("Болісність під час ходьби та сухість шкіри." if index % 4 else ""),
            has_no_complaints=index % 4 == 0,
            comment=f"DEMO-{DEMO_SEED_VERSION}: запис {index + 1:04d}",
            cancellation_reason=("Зміна планів пацієнта." if status_code == "CANCELED" else ""),
        )
        Appointment.objects.filter(pk=appointment.pk).update(
            created_at=local_start - timedelta(days=14),
            updated_at=local_start - timedelta(days=1),
        )
        appointments.append(appointment)
        record_audit_event(
            actor=admin,
            action=AuditAction.APPOINTMENT_CREATED,
            object_type="appointment",
            object_id=appointment.pk,
            object_label=appointment.public_number,
            correlation_id=_correlation("appointments", index + 1),
            after={
                "patient_id": patient.pk,
                "specialist_id": specialist.pk,
                "status": initial_status,
                "starts_at": local_start,
            },
            description="Створено демонстраційний запис у календарі.",
        )

        if status_code not in {"COMPLETED", "IN_PROGRESS"}:
            continue
        visit, _ = start_visit(
            actor=specialist,
            appointment_id=appointment.pk,
            requested_version=appointment.version,
            correlation_id=_correlation("visit-start", index + 1),
        )
        selected_lot = usable_lots[index % len(usable_lots)]
        service_lines = [{"service_id": service.pk, "quantity": 1}]
        if index % 3 == 0:
            additional = active_services[(index + 1) % len(active_services)]
            if additional.pk != service.pk:
                service_lines.append({"service_id": additional.pk, "quantity": 1})
        visit = save_visit_draft(
            actor=specialist,
            visit_id=visit.pk,
            requested_version=visit.version,
            correlation_id=_correlation("visit-draft", index + 1),
            data={
                "complaints": appointment.complaints,
                "has_no_complaints": appointment.has_no_complaints,
                "objective_examination": (
                    "Шкіра суха, локальний гіперкератоз, ознак гострого запалення немає."
                ),
                "detected_conditions": [
                    DetectedCondition.HYPERKERATOSIS,
                    *([DetectedCondition.FISSURES] if index % 5 == 0 else []),
                ],
                "podologist_notes": "Виконано апаратну обробку та надано рекомендації.",
                "service_lines": service_lines,
                "material_lines": [
                    {
                        "lot_id": selected_lot.pk,
                        "quantity": Decimal("0.250"),
                    }
                ],
            },
        )
        if status_code == "COMPLETED":
            finish_visit(
                actor=specialist,
                visit_id=visit.pk,
                idempotency_key=f"demo-finish-{DEMO_SEED_VERSION}-{index + 1:04d}",
                correlation_id=_correlation("visit-finish", index + 1),
                data={
                    "version": visit.version,
                    "recommendations": (
                        "Щодня наносити рекомендований засіб; контроль через 4–6 тижнів."
                    ),
                    "payment_handoff_requested": index % 5 != 0,
                    "follow_up": None,
                },
            )
            Visit.objects.filter(pk=visit.pk).update(
                started_at=local_start,
                completed_at=local_start + timedelta(minutes=service.duration_minutes),
                updated_at=local_start + timedelta(minutes=service.duration_minutes),
            )
        else:
            Visit.objects.filter(pk=visit.pk).update(
                started_at=local_start,
                updated_at=local_start,
            )
        visits.append(Visit.objects.get(pk=visit.pk))
    return appointments, visits


def _jpeg_pair(index: int, kind: str) -> tuple[bytes, bytes]:
    before = kind == VisitPhotoKind.BEFORE
    base = (176, 118 + index % 70, 92) if before else (104, 152, 112 + index % 60)
    image = Image.new("RGB", (640, 480), base)
    preview = image.resize((320, 240))
    full_buffer = BytesIO()
    preview_buffer = BytesIO()
    image.save(full_buffer, format="JPEG", quality=86)
    preview.save(preview_buffer, format="JPEG", quality=80)
    return full_buffer.getvalue(), preview_buffer.getvalue()


def _create_visit_photos(
    *,
    visits: list[Visit],
    count: int,
    uploaded_keys: list[str],
) -> None:
    completed = [visit for visit in visits if visit.status == "COMPLETED"][:count]
    for index, visit in enumerate(completed, start=1):
        for kind in (VisitPhotoKind.BEFORE, VisitPhotoKind.AFTER):
            full, preview = _jpeg_pair(index, kind)
            suffix = kind.lower()
            object_key = f"demo-seed/{DEMO_SEED_VERSION}/photo-{index:03d}-{suffix}.jpg"
            preview_key = f"demo-seed/{DEMO_SEED_VERSION}/photo-{index:03d}-{suffix}-preview.jpg"
            put_private_object(
                object_key=object_key,
                content=full,
                content_type="image/jpeg",
            )
            uploaded_keys.append(object_key)
            put_private_object(
                object_key=preview_key,
                content=preview,
                content_type="image/jpeg",
            )
            uploaded_keys.append(preview_key)
            photo = VisitPhoto.objects.create(
                visit=visit,
                kind=kind,
                object_key=object_key,
                content_type="image/jpeg",
                size=len(full),
                width=640,
                height=480,
                original_name=f"demo-{index:03d}-{suffix}.jpg",
                preview_object_key=preview_key,
                preview_content_type="image/jpeg",
                preview_status=VisitPhotoPreviewStatus.READY,
                created_by=visit.specialist,
            )
            record_audit_event(
                actor=visit.specialist,
                action=AuditAction.VISIT_PHOTO_ADDED,
                object_type="visit_photo",
                object_id=photo.pk,
                object_label=f"{visit.public_number} · {kind}",
                correlation_id=_correlation("photos", index),
                after={"visit_id": visit.pk, "kind": kind, "size": len(full)},
                description="Додано синтетичне демонстраційне фото.",
            )


def _create_finance_payments(
    *,
    receptionists: list[User],
) -> list[Payment]:
    actor = receptionists[0]
    open_cash_shift(actor=actor, correlation_id=_correlation("cash-open"))
    post_cash_movement(
        actor=actor,
        correlation_id=_correlation("cash-deposit"),
        idempotency_key=f"demo-deposit-{DEMO_SEED_VERSION}",
        data={
            "type": "DEPOSIT",
            "amount_minor": 500000,
            "reason": "Стартова розмінна монета",
            "comment": "Демонстраційне внесення.",
        },
    )
    receivables = list(
        Receivable.objects.select_related("visit")
        .filter(status="OPEN")
        .order_by("visit__completed_at", "pk")
    )
    paid: list[Payment] = []
    pay_limit = max(1, int(len(receivables) * 0.68))
    methods = (PaymentMethod.CASH, PaymentMethod.CARD, PaymentMethod.TRANSFER)
    for index, receivable in enumerate(receivables[:pay_limit], start=1):
        payment, _ = post_payment(
            actor=actor,
            correlation_id=_correlation("payments", index),
            idempotency_key=f"demo-payment-{DEMO_SEED_VERSION}-{index:04d}",
            data={
                "visit_id": receivable.visit_id,
                "payment_method": methods[index % len(methods)],
                "comment": "Демонстраційна повна оплата.",
            },
        )
        paid.append(payment)
    return paid


def _create_finance_refunds_and_current_shift(
    *,
    receptionists: list[User],
    paid: list[Payment],
) -> None:
    actor = receptionists[0]
    shift = CashShift.objects.get(employee=actor, status="OPEN")
    for index, payment in enumerate(paid[::12], start=1):
        post_refund(
            actor=actor,
            correlation_id=_correlation("refunds", index),
            idempotency_key=f"demo-refund-{DEMO_SEED_VERSION}-{index:03d}",
            payment_id=payment.pk,
            data={"reason": "Демонстраційне повернення за погодженням адміністратора."},
        )
    post_cash_movement(
        actor=actor,
        correlation_id=_correlation("cash-withdrawal"),
        idempotency_key=f"demo-withdrawal-{DEMO_SEED_VERSION}",
        data={
            "type": "WITHDRAWAL",
            "amount_minor": 100000,
            "reason": "Передача надлишку в сейф",
            "comment": "Демонстраційне вилучення.",
        },
    )
    operations_count = CashLedgerEntry.objects.filter(cash_shift=shift).count()
    expected_cash = available_cash_minor(shift)
    close_cash_shift(
        actor=actor,
        shift_id=shift.pk,
        correlation_id=_correlation("cash-close"),
        idempotency_key=f"demo-close-{DEMO_SEED_VERSION}",
        data={
            "actual_cash_minor": expected_cash,
            "expected_operations_count": operations_count,
            "cash_count_confirmed": True,
            "comment": "",
        },
    )
    current_actor = receptionists[-1]
    open_cash_shift(actor=current_actor, correlation_id=_correlation("cash-current-open"))
    post_cash_movement(
        actor=current_actor,
        correlation_id=_correlation("cash-current-deposit"),
        idempotency_key=f"demo-current-deposit-{DEMO_SEED_VERSION}",
        data={
            "type": "DEPOSIT",
            "amount_minor": 250000,
            "reason": "Поточна розмінна монета",
            "comment": "Відкрита демонстраційна зміна.",
        },
    )


def _record_phase_marker(*, admin: User, correlation_id: str, scale_name: str) -> None:
    record_audit_event(
        actor=admin,
        action=AuditAction.SETTINGS_UPDATED,
        object_type="demo_seed",
        object_id=DEMO_SEED_VERSION,
        object_label=f"Demo seed {DEMO_SEED_VERSION}",
        correlation_id=correlation_id,
        after={"seed_version": DEMO_SEED_VERSION, "scale": scale_name},
        description="Зафіксовано завершення фази демонстраційного наповнення.",
    )


def _create_work_items_and_notifications(
    *,
    admin: User,
    scale: DemoScale,
    patients: list[Patient],
    podologists: list[User],
    receptionists: list[User],
) -> None:
    assignees = [*receptionists, *[user for user in podologists if user.is_active]]
    kinds = tuple(WorkItemKind.values)
    now = timezone.now()
    for index in range(scale.work_items):
        completed = index % 4 == 0
        assignee = assignees[index % len(assignees)]
        patient = patients[(index * 5) % len(patients)]
        item = WorkItem.objects.create(
            kind=kinds[index % len(kinds)],
            title=f"DEMO: справа {index + 1:03d} · {patient.display_name}",
            due_at=now + timedelta(days=(index % 30) - 12, hours=index % 8),
            assignee=assignee,
            patient=patient if kinds[index % len(kinds)] == WorkItemKind.CALLBACK else None,
            comment="Синтетична справа для перевірки фільтрів і станів.",
            is_important=index % 7 == 0,
            is_completed=completed,
            completed_at=now - timedelta(days=index % 10) if completed else None,
            completed_by=admin if completed else None,
            created_by=admin,
        )
        record_audit_event(
            actor=admin,
            action=(
                AuditAction.WORK_ITEM_COMPLETED if completed else AuditAction.WORK_ITEM_CREATED
            ),
            object_type="work_item",
            object_id=item.pk,
            object_label=item.title,
            correlation_id=_correlation("work-items", index + 1),
            after={
                "kind": item.kind,
                "assignee_id": item.assignee_id,
                "is_completed": item.is_completed,
                "is_important": item.is_important,
            },
            description="Створено демонстраційну внутрішню справу.",
        )

    notification_kinds = tuple(NotificationKind.values)
    tones = tuple(NotificationTone.values)
    recipients = [admin, *assignees]
    target_count = max(scale.work_items, len(recipients) * 4)
    for index in range(target_count):
        recipient = recipients[index % len(recipients)]
        notification = Notification.objects.create(
            recipient=recipient,
            event_key=f"demo-seed:{DEMO_SEED_VERSION}:notification:{index:04d}",
            kind=notification_kinds[index % len(notification_kinds)],
            title=f"Демонстраційне сповіщення {index + 1:03d}",
            message="Синтетична подія для перевірки центру сповіщень.",
            tone=tones[index % len(tones)],
            is_important=index % 9 == 0,
            deep_link=("/work-items" if index % 2 else "/calendar"),
            occurred_at=now - timedelta(hours=index % 96),
        )
        if index % 3 == 0:
            Notification.objects.filter(pk=notification.pk).update(read_at=timezone.now())


def seed_demo_data(*, scale_name: str) -> dict[str, Any]:
    scale = DEMO_SCALES[scale_name]
    admin, phase = _preflight(scale_name=scale_name)
    if phase == "complete":
        return {
            "status": "already_seeded",
            "seed_version": DEMO_SEED_VERSION,
            "scale": scale_name,
            "counts": _current_counts(),
        }

    if phase == "empty":
        uploaded_keys: list[str] = []
        try:
            with transaction.atomic():
                podologists, receptionists, _ = _create_users(
                    admin=admin,
                    scale=scale,
                )
                rooms, services = _configure_clinic(admin=admin, scale=scale)
                patients = _create_patients(
                    admin=admin,
                    podologists=podologists,
                    count=scale.patients,
                )
                _, _, lots = _create_inventory(admin=admin, scale=scale)
                _, visits = _create_appointments_and_visits(
                    admin=admin,
                    scale=scale,
                    podologists=podologists,
                    rooms=rooms,
                    services=services,
                    patients=patients,
                    lots=lots,
                )
                _create_visit_photos(
                    visits=visits,
                    count=scale.photo_visits,
                    uploaded_keys=uploaded_keys,
                )
                _create_work_items_and_notifications(
                    admin=admin,
                    scale=scale,
                    patients=patients,
                    podologists=podologists,
                    receptionists=receptionists,
                )
                _record_phase_marker(
                    admin=admin,
                    correlation_id=DEMO_CORE_MARKER,
                    scale_name=scale_name,
                )
        except Exception:
            for object_key in reversed(uploaded_keys):
                delete_private_object(object_key=object_key)
            raise
        phase = "core"

    receptionists = list(
        User.objects.filter(
            email__startswith="demo.reception.",
            email__endswith="@podoria.test",
        ).order_by("email")
    )
    if not receptionists:
        raise ValueError("Demo core phase is marked complete, but reception users are missing.")

    if phase == "core":
        with transaction.atomic():
            _create_finance_payments(receptionists=receptionists)
            _record_phase_marker(
                admin=admin,
                correlation_id=DEMO_PAYMENTS_MARKER,
                scale_name=scale_name,
            )
        phase = "payments"

    if phase == "payments":
        paid = list(Payment.objects.select_related("ledger_entry").order_by("ledger_entry_id"))
        with transaction.atomic():
            _create_finance_refunds_and_current_shift(
                receptionists=receptionists,
                paid=paid,
            )
            _record_phase_marker(
                admin=admin,
                correlation_id=DEMO_COMPLETE_MARKER,
                scale_name=scale_name,
            )

    podologists = list(
        User.objects.filter(
            email__startswith="demo.podologist.",
            email__endswith="@podoria.test",
        ).order_by("email")
    )
    return {
        "status": "seeded",
        "seed_version": DEMO_SEED_VERSION,
        "scale": scale_name,
        "counts": _current_counts(),
        "demo_accounts": {
            "admin": "demo.admin.01@podoria.test",
            "reception": [user.email for user in receptionists],
            "podologists": [user.email for user in podologists],
            "passwords": "unusable",
        },
    }
