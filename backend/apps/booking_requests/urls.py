from django.urls import path

from apps.booking_requests.views import (
    BookingRequestApiCredentialRotateView,
    BookingRequestApiCredentialView,
    BookingRequestDetailView,
    BookingRequestListView,
    BookingRequestProcessView,
    ExternalBookingRequestCreateView,
    TelegramLinkIntentView,
    TelegramSubscriptionView,
    TelegramWebhookView,
)

urlpatterns = [
    path(
        "booking-request-integration",
        BookingRequestApiCredentialView.as_view(),
        name="booking-request-integration",
    ),
    path(
        "booking-request-integration/token/rotate",
        BookingRequestApiCredentialRotateView.as_view(),
        name="booking-request-integration-token-rotate",
    ),
    path(
        "integrations/booking-requests",
        ExternalBookingRequestCreateView.as_view(),
        name="external-booking-request-create",
    ),
    path(
        "integrations/telegram/webhook",
        TelegramWebhookView.as_view(),
        name="telegram-webhook",
    ),
    path("telegram/subscription", TelegramSubscriptionView.as_view(), name="telegram-subscription"),
    path("telegram/link-intents", TelegramLinkIntentView.as_view(), name="telegram-link-intent"),
    path(
        "booking-requests",
        BookingRequestListView.as_view(),
        name="booking-request-list",
    ),
    path(
        "booking-requests/<uuid:booking_request_id>",
        BookingRequestDetailView.as_view(),
        name="booking-request-detail",
    ),
    path(
        "booking-requests/<uuid:booking_request_id>/process",
        BookingRequestProcessView.as_view(),
        name="booking-request-process",
    ),
]
