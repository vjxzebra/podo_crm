from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.booking_requests.models import (
    BookingRequestStatus,
    TelegramDelivery,
    TelegramDeliveryStatus,
)
from apps.booking_requests.telegram_services import dispatch_due_telegram_deliveries


class Command(BaseCommand):
    help = "Show safe Telegram delivery status counts and optionally dispatch due work."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dispatch-due",
            action="store_true",
            help="Run one due-delivery dispatch pass after printing current counts.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        counts = {
            row["status"]: row["count"]
            for row in TelegramDelivery.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        }
        stale_sent = TelegramDelivery.objects.filter(
            status=TelegramDeliveryStatus.SENT,
            message_id__isnull=False,
            booking_request__status=BookingRequestStatus.PROCESSED,
            last_synced_request_version__lt=F("booking_request__version"),
        ).count()
        due_retry = TelegramDelivery.objects.filter(
            Q(status=TelegramDeliveryStatus.PENDING)
            | Q(status=TelegramDeliveryStatus.RETRY, next_attempt_at__lte=timezone.now())
        ).count()
        self.stdout.write("Telegram delivery status:")
        for status in TelegramDeliveryStatus.values:
            self.stdout.write(f"- {status}: {counts.get(status, 0)}")
        self.stdout.write(f"- STALE_SENT: {stale_sent}")
        self.stdout.write(f"- DUE_OR_PENDING: {due_retry}")
        if options["dispatch_due"]:
            dispatched = dispatch_due_telegram_deliveries()
            self.stdout.write(self.style.SUCCESS(f"Dispatched {dispatched} Telegram deliveries."))
