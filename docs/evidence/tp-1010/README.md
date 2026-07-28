# TP-1010 — Telegram authorization та fan-out

Статус: `done` 2026-07-28.

## Реалізований scope

- Додано digest-only `TelegramLinkIntent`, персональну `TelegramSubscription`,
  dedupe inbox `TelegramUpdate` і durable outbox `TelegramDelivery`.
- Admin/reception можуть відкрити Telegram dialog у shell, побачити поточний
  статус, створити одноразовий private deep link, скопіювати його, відкрити
  Telegram і відключити підписку.
- Webhook приймає лише запити з `X-Telegram-Bot-Api-Secret-Token`, обмежує body
  64 KiB, дедуплікує `update_id` і не вимагає session/CSRF.
- `/start <payload>` прив'язує лише private chat, one-time payload, eligible
  admin/reception і унікальну Telegram identity; `/stop` вимикає підписку.
- Нові заявки створюють delivery rows на всі enabled eligible subscriptions до
  broker enqueue, а dispatcher підтримує stored `message_id`, retry/backoff,
  `retry_after` і blocked-chat disable.
- Додано env/file-secret settings і management command
  `configure_telegram_webhook` з `getMe`, username check, HTTPS URL і
  explicit `--drop-pending-updates`.

## Автоматизовані gates

- Focused backend:
  `tests/booking_requests/test_telegram_integration.py`,
  `test_booking_requests_api.py`,
  `test_booking_request_integration_api.py` — `25/25`.
- Canonical backend `pytest` — `440/440`.
- Frontend `vitest` — `227/227`; новий `TelegramDialog` має `2/2` scenarios.
- Ruff format/check, mypy, Django `check`, migration check, compileall,
  OpenAPI snapshot, generated TypeScript schema, contracts, ESLint,
  strict typecheck і production build — green.
- Production web image rebuild виконав внутрішній `npm run check`: contracts,
  lint, typecheck, `227/227` tests і build green.

## Live browser QA

- Через `http://127.0.0.1:8088/booking-requests` створено локального admin із
  credentials тільки в Git-ignored `.env.local`.
- Desktop dialog: `Telegram-сповіщення` відкриває modal, disconnected state
  видимий, `Підключити` створює `https://t.me/podo_crm_pod_bot?start=...`,
  link збігається з read-only полем, controls мають мінімум `44px`,
  horizontal overflow `0`.
- Mobile `390×844`: Telegram dialog вміщується у viewport, horizontal overflow
  `0`, controls мають мінімум `44px`, console warnings/errors `0`.
- Тимчасовий link intent після browser gate видалено; plaintext payload не
  зберігався.

## Runtime recovery

Після rebuild web/backend proxy тимчасово тримав stale upstream IP і readiness
повернув `502`. Перевірено `docker compose ps` і logs backend/proxy/worker/beat:
backend був healthy, worker бачив нові Telegram tasks, а proxy логував
`connect() failed` на старий upstream. Точковий `docker compose restart proxy`
повернув `/health/ready` до `200`.

## Security і hygiene

- Реальний Telegram bot token не використовувався і не записувався у tracked
  files, тестові output або evidence.
- Webhook secret і bot token налаштовані тільки через env/file secrets.
- Telegram chat/user IDs не пишуться в audit snapshots; linked/unlinked events
  фіксують лише PII-safe booleans/timestamps.
- Оприлюднений раніше bot token лишається скомпрометованим і має бути
  відкликаний перед production TP-1011.
