from enum import StrEnum

from apps.accounts.models import User, UserRole


class AccessScope(StrEnum):
    WORKSPACE = "workspace"
    CALENDAR_OWN = "calendar:own"
    CALENDAR_SHARED = "calendar:shared"
    PATIENT_SAFE = "patient:safe"
    MEDICAL = "medical"
    WORK_ITEMS = "work-items"
    BOOKING_REQUESTS = "booking-requests"
    FINANCE = "finance"
    CASH_SHIFT = "cash-shift"
    INVENTORY = "inventory"
    ANALYTICS = "analytics"
    TEAM = "team"
    AUDIT = "audit"
    SETTINGS = "settings"


ALL_SCOPES = frozenset(AccessScope)

ROLE_SCOPES: dict[str, frozenset[AccessScope]] = {
    UserRole.PODOLOGIST: frozenset(
        {
            AccessScope.WORKSPACE,
            AccessScope.CALENDAR_OWN,
            AccessScope.PATIENT_SAFE,
            AccessScope.MEDICAL,
            AccessScope.WORK_ITEMS,
        }
    ),
    UserRole.RECEPTION: frozenset(
        {
            AccessScope.WORKSPACE,
            AccessScope.CALENDAR_SHARED,
            AccessScope.PATIENT_SAFE,
            AccessScope.WORK_ITEMS,
            AccessScope.BOOKING_REQUESTS,
            AccessScope.FINANCE,
            AccessScope.CASH_SHIFT,
        }
    ),
    UserRole.ADMIN: ALL_SCOPES,
}

ROLE_ROUTE_IDS: dict[str, tuple[str, ...]] = {
    UserRole.PODOLOGIST: (
        "overview",
        "calendar",
        "patients",
        "work-items",
        "notifications",
    ),
    UserRole.RECEPTION: (
        "overview",
        "calendar",
        "patients",
        "work-items",
        "booking-requests",
        "finance",
        "notifications",
    ),
    UserRole.ADMIN: (
        "overview",
        "calendar",
        "patients",
        "work-items",
        "booking-requests",
        "finance",
        "inventory",
        "analytics",
        "notifications",
        "team",
        "audit",
        "settings",
        "password-resets",
        "contracts",
    ),
}


def has_scope(user: User, scope: AccessScope) -> bool:
    return user.is_active and scope in ROLE_SCOPES.get(user.role, frozenset())


def route_ids_for(user: User) -> tuple[str, ...]:
    if not user.is_active:
        return ()
    return ROLE_ROUTE_IDS.get(user.role, ())
