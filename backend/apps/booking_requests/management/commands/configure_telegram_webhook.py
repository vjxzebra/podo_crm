from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.booking_requests.telegram_transport import TelegramBotClient, TelegramTransportError


class Command(BaseCommand):
    help = "Configure the Telegram webhook using environment or file-mounted secrets."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--drop-pending-updates",
            action="store_true",
            help="Explicitly ask Telegram to discard pending updates while setting the webhook.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN_FILE is required.")
        if not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError(
                "TELEGRAM_WEBHOOK_SECRET or TELEGRAM_WEBHOOK_SECRET_FILE is required."
            )
        username = str(settings.TELEGRAM_BOT_USERNAME).strip().lstrip("@")
        public_url = str(settings.CRM_PUBLIC_URL).rstrip("/")
        if not public_url.startswith("https://"):
            raise CommandError("CRM_PUBLIC_URL must be HTTPS for Telegram webhook setup.")
        client = TelegramBotClient()
        try:
            me = client.get_me()
        except TelegramTransportError as exc:
            raise CommandError(f"Telegram getMe failed: {exc.code}.") from exc
        actual_username = str(me.get("username") or "").lstrip("@")
        if actual_username != username:
            raise CommandError("Telegram bot username does not match TELEGRAM_BOT_USERNAME.")
        try:
            client.set_webhook(
                url=f"{public_url}/api/v1/integrations/telegram/webhook",
                secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=bool(options["drop_pending_updates"]),
            )
        except TelegramTransportError as exc:
            raise CommandError(f"Telegram setWebhook failed: {exc.code}.") from exc
        self.stdout.write(self.style.SUCCESS(f"Telegram webhook configured for @{username}."))
