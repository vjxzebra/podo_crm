from enum import StrEnum


class AuditSection(StrEnum):
    ACCOUNTS = "accounts"
    TEAM = "team"
    SETTINGS = "settings"
    PATIENTS = "patients"
    WORK_ITEMS = "work_items"
    SCHEDULING = "scheduling"
    MEDICAL = "medical"
    VISITS = "visits"
    BILLING = "billing"
    CASH = "cash"
    INVENTORY = "inventory"


class AuditAction(StrEnum):
    PASSWORD_CHANGED = "accounts.password_changed"  # noqa: S105
    PASSWORD_RESET_REQUESTED = "accounts.password_reset_requested"  # noqa: S105
    TEMPORARY_PASSWORD_SET = "accounts.temporary_password_set"  # noqa: S105

    USER_CREATED = "team.user_created"
    USER_UPDATED = "team.user_updated"
    USER_ROLE_CHANGED = "team.user_role_changed"
    USER_DEACTIVATED = "team.user_deactivated"
    USER_REACTIVATED = "team.user_reactivated"

    SETTINGS_UPDATED = "settings.updated"
    CLINIC_PROFILE_UPDATED = "settings.clinic_profile_updated"
    CLINIC_LOGO_UPDATED = "settings.clinic_logo_updated"
    ROOM_CREATED = "settings.room_created"
    ROOM_UPDATED = "settings.room_updated"
    ROOM_DEACTIVATED = "settings.room_deactivated"
    ROOM_REACTIVATED = "settings.room_reactivated"
    SERVICE_CREATED = "settings.service_created"
    SERVICE_UPDATED = "settings.service_updated"
    SERVICE_DEACTIVATED = "settings.service_deactivated"
    SERVICE_REACTIVATED = "settings.service_reactivated"
    APPOINTMENT_STATUS_CONFIG_UPDATED = "settings.appointment_status_config_updated"
    CLINIC_SCHEDULE_UPDATED = "settings.clinic_schedule_updated"

    PATIENT_CREATED = "patients.patient_created"
    PATIENT_UPDATED = "patients.patient_updated"
    MEDICAL_RECORD_UPDATED = "medical.record_updated"

    WORK_ITEM_CREATED = "work_items.work_item_created"
    WORK_ITEM_UPDATED = "work_items.work_item_updated"
    WORK_ITEM_COMPLETED = "work_items.work_item_completed"
    WORK_ITEM_REOPENED = "work_items.work_item_reopened"

    APPOINTMENT_CREATED = "scheduling.appointment_created"
    APPOINTMENT_UPDATED = "scheduling.appointment_updated"
    APPOINTMENT_RESCHEDULED = "scheduling.appointment_rescheduled"
    APPOINTMENT_CANCELED = "scheduling.appointment_canceled"
    APPOINTMENT_STATUS_CHANGED = "scheduling.appointment_status_changed"

    VISIT_COMPLETED = "visits.visit_completed"

    PAYMENT_POSTED = "billing.payment_posted"
    REFUND_POSTED = "billing.refund_posted"

    CASH_DEPOSIT_POSTED = "cash.deposit_posted"
    CASH_WITHDRAWAL_POSTED = "cash.withdrawal_posted"
    CASH_SHIFT_OPENED = "cash.shift_opened"
    CASH_SHIFT_CLOSED = "cash.shift_closed"

    STOCK_MOVEMENT_POSTED = "inventory.stock_movement_posted"
    STOCKTAKE_POSTED = "inventory.stocktake_posted"


EVENT_SECTIONS: dict[str, AuditSection] = {
    AuditAction.PASSWORD_CHANGED: AuditSection.ACCOUNTS,
    AuditAction.PASSWORD_RESET_REQUESTED: AuditSection.ACCOUNTS,
    AuditAction.TEMPORARY_PASSWORD_SET: AuditSection.ACCOUNTS,
    AuditAction.USER_CREATED: AuditSection.TEAM,
    AuditAction.USER_UPDATED: AuditSection.TEAM,
    AuditAction.USER_ROLE_CHANGED: AuditSection.TEAM,
    AuditAction.USER_DEACTIVATED: AuditSection.TEAM,
    AuditAction.USER_REACTIVATED: AuditSection.TEAM,
    AuditAction.SETTINGS_UPDATED: AuditSection.SETTINGS,
    AuditAction.CLINIC_PROFILE_UPDATED: AuditSection.SETTINGS,
    AuditAction.CLINIC_LOGO_UPDATED: AuditSection.SETTINGS,
    AuditAction.ROOM_CREATED: AuditSection.SETTINGS,
    AuditAction.ROOM_UPDATED: AuditSection.SETTINGS,
    AuditAction.ROOM_DEACTIVATED: AuditSection.SETTINGS,
    AuditAction.ROOM_REACTIVATED: AuditSection.SETTINGS,
    AuditAction.SERVICE_CREATED: AuditSection.SETTINGS,
    AuditAction.SERVICE_UPDATED: AuditSection.SETTINGS,
    AuditAction.SERVICE_DEACTIVATED: AuditSection.SETTINGS,
    AuditAction.SERVICE_REACTIVATED: AuditSection.SETTINGS,
    AuditAction.APPOINTMENT_STATUS_CONFIG_UPDATED: AuditSection.SETTINGS,
    AuditAction.CLINIC_SCHEDULE_UPDATED: AuditSection.SETTINGS,
    AuditAction.PATIENT_CREATED: AuditSection.PATIENTS,
    AuditAction.PATIENT_UPDATED: AuditSection.PATIENTS,
    AuditAction.MEDICAL_RECORD_UPDATED: AuditSection.MEDICAL,
    AuditAction.WORK_ITEM_CREATED: AuditSection.WORK_ITEMS,
    AuditAction.WORK_ITEM_UPDATED: AuditSection.WORK_ITEMS,
    AuditAction.WORK_ITEM_COMPLETED: AuditSection.WORK_ITEMS,
    AuditAction.WORK_ITEM_REOPENED: AuditSection.WORK_ITEMS,
    AuditAction.APPOINTMENT_CREATED: AuditSection.SCHEDULING,
    AuditAction.APPOINTMENT_UPDATED: AuditSection.SCHEDULING,
    AuditAction.APPOINTMENT_RESCHEDULED: AuditSection.SCHEDULING,
    AuditAction.APPOINTMENT_CANCELED: AuditSection.SCHEDULING,
    AuditAction.APPOINTMENT_STATUS_CHANGED: AuditSection.SCHEDULING,
    AuditAction.VISIT_COMPLETED: AuditSection.VISITS,
    AuditAction.PAYMENT_POSTED: AuditSection.BILLING,
    AuditAction.REFUND_POSTED: AuditSection.BILLING,
    AuditAction.CASH_DEPOSIT_POSTED: AuditSection.CASH,
    AuditAction.CASH_WITHDRAWAL_POSTED: AuditSection.CASH,
    AuditAction.CASH_SHIFT_OPENED: AuditSection.CASH,
    AuditAction.CASH_SHIFT_CLOSED: AuditSection.CASH,
    AuditAction.STOCK_MOVEMENT_POSTED: AuditSection.INVENTORY,
    AuditAction.STOCKTAKE_POSTED: AuditSection.INVENTORY,
}
