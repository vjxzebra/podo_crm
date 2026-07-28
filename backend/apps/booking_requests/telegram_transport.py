import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger("podoria")


class TelegramTransportError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class TelegramMessageResult:
    message_id: int


class TelegramBotClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        api_base_url: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.token = token if token is not None else settings.TELEGRAM_BOT_TOKEN
        self.api_base_url = (api_base_url or settings.TELEGRAM_API_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.TELEGRAM_REQUEST_TIMEOUT_SECONDS
        parsed_base = urlsplit(self.api_base_url)
        if parsed_base.scheme != "https" or not parsed_base.netloc:
            raise TelegramTransportError(
                code="invalid_api_base_url",
                message="Telegram API base URL must be an HTTPS URL.",
            )

    def get_me(self) -> dict[str, Any]:
        payload = self._request("getMe", {})
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    def set_webhook(
        self,
        *,
        url: str,
        secret_token: str,
        allowed_updates: list[str],
        drop_pending_updates: bool = False,
    ) -> dict[str, Any]:
        payload = self._request(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": allowed_updates,
                "drop_pending_updates": drop_pending_updates,
            },
        )
        result = payload.get("result")
        return {"ok": bool(result)}

    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> TelegramMessageResult:
        body: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        payload = self._request("sendMessage", body)
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise TelegramTransportError(code="bad_response", message="Bad Telegram response.")
        return TelegramMessageResult(message_id=result["message_id"])

    def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        self._request("editMessageText", body)

    def answer_callback_query(self, *, callback_query_id: str, text: str = "") -> None:
        body: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": False,
        }
        if text:
            body["text"] = text[:200]
        self._request("answerCallbackQuery", body)

    def _request(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise TelegramTransportError(
                code="not_configured", message="Telegram bot token is not configured."
            )
        url = f"{self.api_base_url}/bot{self.token}/{method}"
        request = Request(  # noqa: S310 - api_base_url is validated to HTTPS during client setup.
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            retry_after = None
            description = "Telegram HTTP error."
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                error_payload = {}
            if isinstance(error_payload, dict):
                parameters = error_payload.get("parameters")
                if isinstance(parameters, dict) and isinstance(parameters.get("retry_after"), int):
                    retry_after = parameters["retry_after"]
                if isinstance(error_payload.get("description"), str):
                    description = error_payload["description"][:255]
            raise TelegramTransportError(
                code=f"http_{exc.code}",
                message=description,
                status_code=exc.code,
                retry_after=retry_after,
            ) from exc
        except (OSError, URLError, TimeoutError) as exc:
            raise TelegramTransportError(
                code="network_error", message="Telegram network error."
            ) from exc
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            api_description: object = (
                payload.get("description") if isinstance(payload, dict) else None
            )
            raise TelegramTransportError(
                code="api_error",
                message=(
                    api_description if isinstance(api_description, str) else "Telegram API error."
                )[:255],
            )
        return payload
