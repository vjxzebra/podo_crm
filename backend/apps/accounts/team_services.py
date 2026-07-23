from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.accounts.services import revoke_user_sessions
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from config.api.exceptions import ApiProblem


def team_user_snapshot(user: User) -> dict[str, Any]:
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "temporary_password_expires_at": user.temporary_password_expires_at,
    }


def _temporary_password_expiry(*, is_active: bool, must_change_password: bool) -> datetime | None:
    if not is_active or not must_change_password:
        return None
    return timezone.now() + timedelta(hours=settings.TEMPORARY_PASSWORD_TTL_HOURS)


@transaction.atomic
def create_team_user(
    *,
    actor: User,
    correlation_id: str,
    data: dict[str, Any],
) -> User:
    must_change_password = bool(data["must_change_password"])
    is_active = bool(data["is_active"])
    user = User.objects.create_user(
        email=data["email"],
        password=data["temporary_password"],
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        phone=data.get("phone", "").strip(),
        role=data["role"],
        is_active=is_active,
        must_change_password=must_change_password,
        temporary_password_expires_at=_temporary_password_expiry(
            is_active=is_active,
            must_change_password=must_change_password,
        ),
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.USER_CREATED,
        object_type="user",
        object_id=user.pk,
        object_label=user.display_name,
        correlation_id=correlation_id,
        before={},
        after=team_user_snapshot(user),
        description="Створено профіль працівника.",
    )
    return user


def _locked_target_for_update(*, target_id: int, changes: dict[str, Any]) -> User:
    candidate = User.objects.get(pk=target_id)
    next_role = changes.get("role", candidate.role)
    next_active = changes.get("is_active", candidate.is_active)
    removes_active_admin = bool(
        candidate.is_active
        and candidate.role == UserRole.ADMIN
        and (not next_active or next_role != UserRole.ADMIN)
    )
    if not removes_active_admin:
        return User.objects.select_for_update().get(pk=target_id)

    active_admins = list(
        User.objects.select_for_update().filter(role=UserRole.ADMIN, is_active=True).order_by("pk")
    )
    target = next((user for user in active_admins if user.pk == target_id), None)
    if target is None:
        target = User.objects.select_for_update().get(pk=target_id)
    next_role = changes.get("role", target.role)
    next_active = changes.get("is_active", target.is_active)
    if (
        target.is_active
        and target.role == UserRole.ADMIN
        and (not next_active or next_role != UserRole.ADMIN)
        and len(active_admins) <= 1
    ):
        raise ApiProblem(
            code="last_admin_protected",
            message="Не можна деактивувати або змінити роль останнього адміністратора.",
            status_code=409,
        )
    return target


@transaction.atomic
def update_team_user(
    *,
    actor: User,
    target_id: int,
    correlation_id: str,
    changes: dict[str, Any],
) -> User:
    target = _locked_target_for_update(target_id=target_id, changes=changes)
    before = team_user_snapshot(target)
    was_active = target.is_active
    previous_role = target.role

    for field in ("first_name", "last_name", "phone", "email", "role", "is_active"):
        if field in changes:
            value = changes[field]
            if isinstance(value, str):
                value = value.strip()
            setattr(target, field, value)

    if not was_active and target.is_active and target.must_change_password:
        target.temporary_password_expires_at = _temporary_password_expiry(
            is_active=True,
            must_change_password=True,
        )
    target.save()

    if was_active and not target.is_active:
        action = AuditAction.USER_DEACTIVATED
        description = "Деактивовано профіль працівника."
    elif not was_active and target.is_active:
        action = AuditAction.USER_REACTIVATED
        description = "Активовано профіль працівника."
    elif previous_role != target.role:
        action = AuditAction.USER_ROLE_CHANGED
        description = "Змінено роль працівника."
    else:
        action = AuditAction.USER_UPDATED
        description = "Оновлено контактні дані працівника."

    if was_active and (not target.is_active or previous_role != target.role):
        revoke_user_sessions(target)

    record_audit_event(
        actor=actor,
        action=action,
        object_type="user",
        object_id=target.pk,
        object_label=target.display_name,
        correlation_id=correlation_id,
        before=before,
        after=team_user_snapshot(target),
        description=description,
    )
    return target


@transaction.atomic
def deactivate_team_user(
    *,
    actor: User,
    target_id: int,
    correlation_id: str,
) -> User:
    target = User.objects.get(pk=target_id)
    if not target.is_active:
        raise ApiProblem(
            code="user_already_inactive",
            message="Профіль працівника вже деактивовано.",
            status_code=409,
        )
    return update_team_user(
        actor=actor,
        target_id=target_id,
        correlation_id=correlation_id,
        changes={"is_active": False},
    )
