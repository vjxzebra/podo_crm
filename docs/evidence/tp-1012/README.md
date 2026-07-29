# TP-1012 — Telegram-сповіщення про призначені справи

Статус: `done` 2026-07-29.

## Реалізований scope

- Усі active ролі зі scope `work-items`, включно з podologist, можуть
  підключити private Telegram.
- Durable `WorkItemTelegramDelivery` створюється лише для subscription
  поточного assignee; підключення додає його існуючі відкриті справи.
- Повідомлення показує open/overdue/completed/reassigned status, safe details,
  кнопку `✅ Виконати справу` та exact `/work-items?item=<uuid>` CRM link.
- Callback перевіряє exact private Telegram identity, active user, scope і
  поточне assignment, після чого викликає той самий `update_work_item`, що CRM.
- CRM/Telegram completion, reopen, reassignment і due transition
  синхронізуються через best-effort `editMessageText`.
- Booking-request fan-out лишився тільки для admin/reception.
- Operations status command окремо показує safe aggregate counts booking
  request і work-item deliveries.

## Автоматизовані gates

- Focused Telegram/work-item/migration backend — `16/16`.
- Broader work-item/notification/Telegram backend — `36/36`.
- Canonical backend — `450/450`.
- Canonical frontend — `227/227`, із `42/42` accessibility scenarios.
- Ruff check/format для `295` Python files і mypy для `223` source files —
  green.
- Django `check`, migrate/migrate-check, migration reverse/reapply,
  makemigrations dry-run, compileall, OpenAPI snapshot, generated TypeScript
  client, contracts, ESLint, strict typecheck і production build — green.

## Runtime

- Локальна dev database має migration
  `booking_requests.0006_workitemtelegramdelivery`.
- Оновлений production-style web image зібраний і запущений.
- Backend, worker і beat перезапущені; worker зареєстрував booking-request,
  work-item і update Telegram tasks.
- Manual due dispatch повернув нульові safe aggregate counts і завершився
  успішно.
- Наступний реальний beat-цикл виконав
  `dispatch_telegram_work_item_deliveries` успішно.
- `/health/ready` і `/` повернули `200`; unauthenticated `/api/v1/session`
  очікувано повернув `401`.

## Recovery note

Перший runtime log inspection побачив `FOR UPDATE` error від старого worker,
який ще тримав код до виправлення nullable outer join. Worker/beat були
точково перезапущені; manual dispatch і наступний periodic task підтвердили
усунення помилки. Volumes та domain data не видалялися.

## Security і hygiene

- Локальний Telegram token не налаштований; active subscriptions/open work
  items під час runtime gate — `0/0`, зовнішні повідомлення не надсилались.
- Реальні credentials, Telegram chat/user IDs, token, raw update payload,
  phone або patient data не потрапили в tracked evidence.
- Production deployment TP-1012 не виконувався.
