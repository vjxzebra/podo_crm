# TP-1009 — Bearer API заявок і керування токеном

Статус: `done` 2026-07-28.

## Реалізований scope

- Додано singleton credential і submission mapping для зовнішніх заявок.
- Повне значення Bearer token повертається лише один раз; у базі зберігаються
  тільки HMAC digest, безпечний hint, версія та metadata ротації.
- Admin-only API та вкладка `Налаштування → Інтеграції` підтримують перше
  генерування, підтвердження ротації, copy-once і очищення plaintext після
  закриття діалогу.
- `POST /api/v1/integrations/booking-requests` приймає server-to-server заявки
  з Instagram, Facebook і сайту. Поля клієнта лишаються необов’язковими,
  невідомі поля відхиляються.
- `Idempotency-Key` і canonical payload hash дають один create для точного
  повтору та `409` для того самого key зі зміненим payload.
- Окремі rate limits захищають валідний credential і невдалі спроби за IP.
- OpenAPI використовує `bookingRequestBearerAuth`; TypeScript schema та
  [integration guide](../../integrations/booking-requests-api.md) актуальні.

## Автоматизовані gates

- `8` focused backend integration scenarios, включно з RBAC, digest-only
  storage, optional fields, rotation, rate limit і concurrent replay.
- `2` нові frontend integration-settings scenarios; разом App suite має `96`
  scenarios.
- Canonical: `434/434` backend, `225/225` frontend і `42/42` accessibility.
- Ruff/format, mypy, Django checks, clean migrations, OpenAPI snapshot,
  generated TypeScript schema, contracts, ESLint, strict typecheck і
  production build — green.
- Міграцію перевірено forward, reverse і повторним forward застосуванням.

## Live HTTP і browser QA

- Через production proxy перший exact request повернув `201`, повтор — `200`
  з `Idempotent-Replayed: true` і тим самим ID; змінений payload із тим самим
  key повернув `409 idempotency_payload_mismatch`.
- Тимчасову заявку та submission після перевірки видалено; append-only audit
  ротації збережено. Plaintext token не зберігався.
- Admin settings показує лише masked hint і metadata останньої ротації.
- Confirmation dialog попереджає, що старий token припинить діяти негайно;
  `Скасувати` закриває його без ротації та повертає focus на action.
- На `390×844` сторінка не має горизонтального overflow, картки й security
  warning лишаються читабельними; browser console має `0` warning/error.

Артефакти:

- [configured integration](booking-request-integration-configured.png)
- [rotation confirmation](booking-request-token-rotation-confirmation.png)
- [mobile integration](booking-request-integration-mobile.png)

## Runtime recovery

Під час фінального запуску Docker Desktop не отримав exit event старого backend
container. Перевірено точний container, health, exit state і daemon; штатний
restart Docker Desktop перевів stale container у завершений стан, після чого
Compose без видалення volumes відтворив backend. Усі сервіси повернулися в
healthy, migration check чистий, `/health/ready` повертає `200`.

## Security і hygiene

- Старий Bearer token після ротації перевірено як недійсний.
- Authorization, plaintext token, payload із PII та digest не потрапляють в
  API-відповіді, audit snapshots або tracked документацію.
- Оприлюднений Telegram bot token не використовувався і не переносився у
  repository; перед production TP-1011 він має бути відкликаний.
