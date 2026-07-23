from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

SESSION_ISSUED_AT_KEY = "_podoria_session_issued_at"
SESSION_LAST_SEEN_AT_KEY = "_podoria_session_last_seen_at"


def initialize_session_security(request: HttpRequest) -> None:
    now = timezone.now()
    timestamp = now.timestamp()
    request.session[SESSION_ISSUED_AT_KEY] = timestamp
    request.session[SESSION_LAST_SEEN_AT_KEY] = timestamp
    request.session.set_expiry(now + timedelta(seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS))
