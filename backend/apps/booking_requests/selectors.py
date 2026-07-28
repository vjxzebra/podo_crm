from django.db.models import QuerySet

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User
from apps.booking_requests.models import BookingRequest


def booking_requests_visible_to(user: User) -> QuerySet[BookingRequest]:
    if not has_scope(user, AccessScope.BOOKING_REQUESTS):
        return BookingRequest.objects.none()
    return BookingRequest.objects.select_related("processed_by").all()
