# TP-1011 — Telegram callback і cross-chat sync

Статус: `done` 2026-07-28.

## Реалізований scope

- `TelegramUpdate` inbox зберігає тільки allowlisted callback metadata:
  `callback_query_id`, `callback_data`, `chat_type`, `message_id`.
- `TelegramBotClient` підтримує `answerCallbackQuery` і `editMessageText`.
- Callback `br:p:<uuid>` перевіряє private chat, active subscription,
  Telegram identity, active CRM user і `booking-requests` scope.
- Authorized callback викликає той самий `process_booking_request`, що CRM API;
  перший actor/time лишаються authoritative, повторний callback відповідає
  already-processed без другого audit mutation.
- Після CRM або Telegram process stale `SENT` delivery отримують
  `editMessageText`: status стає `✅ Оброблено`, додаються actor/time,
  action button видаляється, CRM link лишається.
- Edit sync є best-effort: 429 поважає `retry_after`, 400/403 стають
  permanent failure, 403 вимикає exact subscription, інші chats не блокуються.
- Додано `telegram_delivery_status` management command для safe aggregate
  status counts і optional due dispatch без chat/user IDs.
- Додано [production Telegram runbook](../../operations/telegram-rollout-runbook.md)
  з placeholder-only secret files, webhook setup і redacted smoke checklist.

## Автоматизовані gates

- Focused backend booking-request/Telegram/API — `29/29`.
- Canonical backend `pytest` — `444/444`.
- Frontend `vitest` — `227/227`.
- Ruff format/check, mypy, Django `check`, migration check, makemigrations
  dry-run, compileall, OpenAPI snapshot, generated TypeScript schema,
  contracts check, ESLint, strict typecheck і production build — green.
- `telegram_delivery_status` runtime command повернув тільки aggregate counts.

## Runtime

- Backend/worker/beat оновлено на свіжий backend image через stateless recreate.
- Worker після recreate містить Telegram delivery/update tasks і `ready`.
- `/health/ready` через proxy повернув `200`; proxy restart не знадобився.
- Production Telegram smoke не виконувався локально, бо реальний bot token має
  бути rotated перед rollout і не зберігається в repository.

## Security і hygiene

- Реальний Telegram bot token/webhook secret не використовувався.
- Evidence не містить Telegram chat/user IDs, raw payload, phone, contact
  handle або customer message.
- Unauthorized callback відповідає safe generic text і не розкриває заявку.
- Повторний callback не змінює першого виконавця й не дублює audit.
