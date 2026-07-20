from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import PasswordResetRequest, User


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
    locked_user.set_password(new_password)
    locked_user.must_change_password = False
    locked_user.temporary_password_expires_at = None
    locked_user.save(
        update_fields=("password", "must_change_password", "temporary_password_expires_at")
    )
    update_session_auth_hash(request, locked_user)
    revoke_user_sessions(locked_user, keep_session_key=request.session.session_key)
    return locked_user


@transaction.atomic
def set_temporary_password(*, actor: User, target: User, temporary_password: str) -> User:
    locked_user = User.objects.select_for_update().get(pk=target.pk)
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
    return locked_user
