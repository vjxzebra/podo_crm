from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import PasswordResetRequest, User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from config.middleware import get_request_id


def revoke_user_sessions(user: User, *, keep_session_key: str | None = None) -> int:
    session_keys: list[str] = []
    sessions: Iterable[Session] = Session.objects.filter(expire_date__gt=timezone.now())
    for session in sessions:
        if session.session_key == keep_session_key:
            continue
        session_user_id = session.get_decoded().get("_auth_user_id")
        if str(session_user_id) == str(user.pk):
            session_keys.append(session.session_key)
    deleted, _ = Session.objects.filter(session_key__in=session_keys).delete()
    return deleted


@transaction.atomic
def change_own_password(request: HttpRequest, user: User, new_password: str) -> User:
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    before = {
        "must_change_password": locked_user.must_change_password,
        "temporary_password_expires_at": locked_user.temporary_password_expires_at,
    }
    locked_user.set_password(new_password)
    locked_user.must_change_password = False
    locked_user.temporary_password_expires_at = None
    locked_user.save(
        update_fields=("password", "must_change_password", "temporary_password_expires_at")
    )
    update_session_auth_hash(request, locked_user)
    revoke_user_sessions(locked_user, keep_session_key=request.session.session_key)
    record_audit_event(
        actor=locked_user,
        action=AuditAction.PASSWORD_CHANGED,
        object_type="user",
        object_id=locked_user.pk,
        object_label=locked_user.display_name,
        correlation_id=get_request_id(request),
        before=before,
        after={
            "must_change_password": False,
            "temporary_password_expires_at": None,
        },
        description="Працівник змінив власний пароль.",
    )
    return locked_user


@transaction.atomic
def set_temporary_password(
    *,
    actor: User,
    target: User,
    temporary_password: str,
    correlation_id: str,
) -> User:
    locked_user = User.objects.select_for_update().get(pk=target.pk)
    before = {
        "must_change_password": locked_user.must_change_password,
        "temporary_password_expires_at": locked_user.temporary_password_expires_at,
    }
    locked_user.set_password(temporary_password)
    locked_user.must_change_password = True
    locked_user.temporary_password_expires_at = timezone.now() + timedelta(
        hours=settings.TEMPORARY_PASSWORD_TTL_HOURS
    )
    locked_user.save(
        update_fields=("password", "must_change_password", "temporary_password_expires_at")
    )
    PasswordResetRequest.objects.filter(user=locked_user, resolved_at__isnull=True).update(
        resolved_at=timezone.now(),
        resolved_by=actor,
    )
    revoke_user_sessions(locked_user)
    record_audit_event(
        actor=actor,
        action=AuditAction.TEMPORARY_PASSWORD_SET,
        object_type="user",
        object_id=locked_user.pk,
        object_label=locked_user.display_name,
        correlation_id=correlation_id,
        before=before,
        after={
            "must_change_password": True,
            "temporary_password_expires_at": locked_user.temporary_password_expires_at,
        },
        description="Адміністратор установив тимчасовий пароль працівнику.",
    )
    return locked_user


@transaction.atomic
def request_password_reset(*, user: User, correlation_id: str) -> PasswordResetRequest:
    reset_request, created = PasswordResetRequest.objects.get_or_create(
        user=user,
        resolved_at__isnull=True,
    )
    if created:
        record_audit_event(
            actor=None,
            actor_display_name="Анонімний користувач",
            actor_role="anonymous",
            action=AuditAction.PASSWORD_RESET_REQUESTED,
            object_type="user",
            object_id=user.pk,
            object_label=user.display_name,
            correlation_id=correlation_id,
            before={},
            after={"reset_request_id": reset_request.pk, "status": "pending"},
            description="Створено запит на відновлення пароля.",
        )
    return reset_request
