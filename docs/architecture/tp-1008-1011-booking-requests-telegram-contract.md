# TP-1008—TP-1011 — заявки на запис, integration API та Telegram-бот

Статус контракту: `frozen` 2026-07-28.

Джерело: запит власника продукту від 2026-07-28.

## 1. Мета і межа

CRM отримує окремий розділ «Заявки» для звернень на запис із трьох джерел:

- Instagram;
- Facebook;
- сайт.

Заявка створюється зовнішньою системою через server-to-server JSON API з
`Authorization: Bearer ...`, з'являється у CRM та асинхронно надсилається всім
підключеним до Telegram-бота працівникам, які мають доступ до заявок.

Працівник може позначити заявку обробленою:

- у CRM;
- inline-кнопкою в Telegram.

PostgreSQL є єдиним authoritative джерелом статусу. Telegram-повідомлення є
проєкцією: після зміни статусу бот best-effort оновлює всі раніше надіслані копії.
Помилка Telegram не відкочує створення або обробку заявки.

## 2. Зафіксовані продуктові рішення

### 2.1. Ролі

| Можливість | Admin | Reception | Podologist | External API |
|---|---:|---:|---:|---:|
| Перегляд розділу «Заявки» | так | так | ні | ні |
| Позначити заявку обробленою | так | так | ні | ні |
| Підключити власний Telegram | так | так | ні | ні |
| Генерувати/ротувати Bearer token | так | ні | ні | ні |
| Створити заявку | ні | ні | ні | так |

Для домену додається `AccessScope.BOOKING_REQUESTS`. Він входить у ролі
`ADMIN` і `RECEPTION`. Route id `booking-requests` повертається лише цим ролям.
Backend scope є authoritative; приховування route у frontend не вважається
контролем доступу.

### 2.2. Статуси

У першій версії існують рівно два статуси:

- `NEW` — нова;
- `PROCESSED` — оброблена.

Редагування, повторне відкриття, видалення, spam/rejected status та автоматичне
створення пацієнта або запису не входять у цей scope.

### 2.3. Два різні секрети

Не можна змішувати:

1. **Bearer token заявок** — генерується admin у CRM, його отримує сайт або
   server-side інтеграція Instagram/Facebook.
2. **Telegram bot token** — видається BotFather, зберігається лише як production
   secret/env/file secret і ніколи не показується у CRM.

Токен Telegram, оприлюднений у початковому запиті, вважається скомпрометованим.
До production rollout він має бути відкликаний у BotFather і замінений новим.
Його значення заборонено переносити в Git, fixtures, logs, evidence або history.

## 3. Доменна модель

Новий Django app: `apps.booking_requests`.

### 3.1. `BookingRequest`

| Поле | Тип / обмеження |
|---|---|
| `id` | UUID, primary key |
| `public_number` | `REQ-` + 10 uppercase hex symbols, unique, immutable |
| `source` | `INSTAGRAM`, `FACEBOOK`, `WEBSITE`, immutable |
| `status` | `NEW` або `PROCESSED`, default `NEW` |
| `client_name` | optional, trimmed, до 160 символів |
| `phone` | optional original display value, до 32 символів; якщо заданий — валідний телефон |
| `phone_normalized` | blank або canonical `+`/digits value, indexed |
| `service` | optional immutable назва/snapshot вибраної послуги, до 160 символів |
| `contact_handle` | optional, trimmed, до 100 символів |
| `message` | optional, trimmed, до 2000 символів |
| `preferred_at` | optional timezone-aware datetime |
| `external_reference` | optional opaque source reference, до 160 символів |
| `processed_by` | nullable `User`, `PROTECT` |
| `processed_by_display_name` | immutable snapshot, blank для `NEW` |
| `processed_at` | nullable datetime |
| `version` | positive integer, default `1` |
| `created_at` | server timestamp |
| `updated_at` | server timestamp |

DB constraints:

- `NEW` вимагає empty `processed_by`, snapshot і `processed_at`;
- `PROCESSED` вимагає всі три processed fields;
- `version >= 1`;
- `public_number` та source/contact payload не змінюються після create;
- hard delete не надається через business API.

Телефон використовує ту саму canonical normalization, що й patient search, але
заявка не створює, не прив'язує і не змінює `Patient`.

### 3.2. `BookingRequestSubmission`

Окремий immutable рядок забезпечує retry-safe external create:

- UUID;
- one-to-one `booking_request`;
- `idempotency_key`, max 128;
- canonical SHA-256 `payload_hash`;
- `created_at`;
- unique `idempotency_key`.

Однаковий key + однаковий payload повертає створену раніше заявку. Однаковий key
з іншим payload повертає `409 idempotency_payload_mismatch`.

### 3.3. `BookingRequestApiCredential`

Singleton `key="booking_requests"`:

- `token_digest` — SHA-256 digest 256-bit random token;
- `token_hint` — безпечний suffix для ідентифікації, не більше 6 символів;
- `rotated_at`, `rotated_by`, `rotated_by_display_name`;
- `version`.

Повний Bearer token не зберігається. Він повертається лише один раз у response
операції generate/rotate. Digest не серіалізується і не потрапляє в audit.

Token format:

```text
podo_req_<base64url random 32 bytes>
```

Ротація атомарно й негайно інвалідовує попередній token. Grace period не
підтримується у першій версії.

### 3.4. Telegram-моделі

`TelegramLinkIntent`:

- UUID;
- user;
- SHA-256 digest одноразового random payload;
- `expires_at` (10 хвилин), nullable `used_at`;
- created timestamp;
- один intent можна використати рівно один раз.

`TelegramSubscription`:

- one-to-one active CRM user;
- unique `telegram_user_id` і unique private `chat_id` (`BigInteger`);
- optional username/first-name snapshots;
- `is_enabled`, `linked_at`, `disabled_at`, `last_seen_at`;
- тільки active `ADMIN`/`RECEPTION` є eligible на delivery або callback.

`TelegramUpdate`:

- unique Telegram `update_id`;
- мінімально необхідний normalized update type і identifiers;
- processing state/attempt/error metadata;
- raw token, Authorization headers та повний довільний payload не зберігаються.

`TelegramDelivery`:

- booking request + subscription;
- chat id snapshot;
- nullable Telegram `message_id`;
- `PENDING`, `SENT`, `RETRY`, `PERMANENT_FAILURE`;
- attempt/next-attempt/sanitized error metadata;
- `last_synced_request_version`;
- unique `(booking_request, subscription)`.

Delivery rows є durable outbox. Періодичний dispatcher підбирає незавершені
delivery навіть якщо перший `transaction.on_commit()` enqueue не дійшов до broker.

## 4. Internal CRM API

Усі paths мають префікс `/api/v1`.

### `GET /booking-requests`

Access: `ADMIN`, `RECEPTION`.

Query:

- `status=NEW|PROCESSED|ALL`, default `NEW`;
- `source=INSTAGRAM|FACEBOOK|WEBSITE|ALL`, default `ALL`;
- `search`, max 100, шукає public number, ім'я, телефон і contact handle;
- `cursor`.

Порядок: `created_at DESC, id DESC`, page size 30.

Response:

```json
{
  "booking_requests": [],
  "counts": {
    "new": 0,
    "processed": 0,
    "total": 0
  },
  "next_cursor": null
}
```

Counts обчислюються в role scope до status/source/search/pagination.

### `GET /booking-requests/{id}`

Повертає повну role-safe projection або generic `404`.

Item:

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "public_number": "REQ-0123456789",
  "source": "INSTAGRAM",
  "status": "NEW",
  "client_name": "Ім'я клієнта",
  "phone": "+380000000000",
  "service": "Консультація подолога",
  "contact_handle": "@client",
  "message": "Хочу записатися",
  "preferred_at": null,
  "external_reference": "",
  "processed_by_display_name": "",
  "processed_at": null,
  "version": 1,
  "created_at": "2026-07-28T10:00:00Z",
  "updated_at": "2026-07-28T10:00:00Z"
}
```

### `POST /booking-requests/{id}/process`

Strict body:

```json
{
  "version": 1
}
```

Service бере row lock. Для `NEW` stale version дає `409 version_conflict`. Перший
успішний виклик встановлює status/snapshots/timestamp, збільшує version і пише
audit у тій самій transaction.

Якщо заявка вже `PROCESSED`, повтор повертає поточну projection з `200`, не змінює
першого виконавця/час і не створює другий audit event. Після commit створюється
Telegram sync work; її помилка не змінює response.

## 5. Налаштування Bearer token

### `GET /booking-request-integration`

Access: `ADMIN`.

Response ніколи не містить token/digest:

```json
{
  "is_configured": true,
  "token_hint": "a1B2c3",
  "rotated_at": "2026-07-28T10:00:00Z",
  "rotated_by_display_name": "Адміністратор",
  "version": 2
}
```

### `POST /booking-request-integration/token/rotate`

Access: `ADMIN`; session auth + CSRF.

Strict body:

```json
{
  "version": 2,
  "confirm": true
}
```

Response повертає metadata та одноразове поле `token`. Endpoint має
`Cache-Control: no-store`; token не потрапляє в telemetry. Concurrent stale
rotation дає `409 version_conflict`.

UI: нова admin-only вкладка «Інтеграції» у `/settings`:

- configured/not configured, token hint, час і автор останньої ротації;
- `Згенерувати токен` для першого створення;
- `Згенерувати новий` для ротації;
- confirm dialog із попередженням про негайне припинення дії старого token;
- one-time dialog з кнопкою copy і явним повідомленням, що повторно показати
  значення неможливо;
- закриття one-time dialog очищає token із React state.

## 6. External booking request API

### `POST /api/v1/integrations/booking-requests`

Це server-to-server endpoint. Session cookie та CSRF не використовуються.

Required headers:

```http
Authorization: Bearer <booking-request-api-token>
Idempotency-Key: <stable value up to 128 characters>
Content-Type: application/json
```

Strict request:

```json
{
  "source": "INSTAGRAM",
  "client_name": "Ім'я клієнта",
  "phone": "+380000000000",
  "service": "Консультація подолога",
  "contact_handle": "@client",
  "message": "Хочу записатися у другій половині дня",
  "preferred_at": "2026-08-01T12:00:00+03:00",
  "external_reference": "lead-123"
}
```

Required: лише технічне поле `source`. Поля форми `client_name`, `phone`,
`service`, `message` необов’язкові; решта contact fields також optional.
Absent string fields нормалізуються до `""`, `preferred_at` — до `null`.
Непорожній `phone` проходить normalizer/validation. Unknown keys дають `422`.

Initial response: `201`. Exact replay: `200` +
`Idempotent-Replayed: true`.

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "public_number": "REQ-0123456789",
  "status": "NEW",
  "created_at": "2026-07-28T10:00:00Z"
}
```

Authentication:

- custom DRF `BookingRequestBearerAuthentication`;
- constant-time digest comparison;
- generic `401 invalid_bearer_token` + `WWW-Authenticate: Bearer`;
- OpenAPI security scheme `bookingRequestBearerAuth`;
- Authorization header redacted у logs/audit.

Rate limits:

- valid token: 60 requests/minute;
- invalid credential attempts: 30/IP за 15 хвилин;
- `429` містить `Retry-After`;
- межі configurable через env.

Зовнішній сайт викликає endpoint лише зі свого backend. Bearer token заборонено
вставляти у browser JavaScript, HTML, GTM, mobile bundle або public repository.

## 7. CRM UI

Новий route `/booking-requests`, label «Заявки», доступний admin/reception.

Обов'язкові стани:

- initial loading, empty, error/retry;
- filter status/source, debounced search, cursor load-more;
- desktop table, tablet/mobile cards без page-level horizontal overflow;
- new count і source badges;
- detail dialog/sheet, URL `?request=<uuid>` відновлюється після reload;
- `Позначити обробленою` з pending, success, generic not-found і conflict refetch;
- already processed read-only state з ім'ям та часом;
- 44px primary targets, keyboard focus trap/return, `Escape`, body lock.

Не додаються edit/delete, bulk processing, manual create, patient conversion або
appointment creation.

## 8. Telegram configuration і transport

Production secrets/config:

- `TELEGRAM_BOT_TOKEN` або file-secret equivalent — secret;
- `TELEGRAM_WEBHOOK_SECRET` або file-secret equivalent — secret;
- `TELEGRAM_BOT_USERNAME=podo_crm_pod_bot` — не secret;
- `CRM_PUBLIC_URL=https://crm.rozhenko.km.ua`;
- enable/timeout/retry parameters.

Bot token та webhook secret не зберігаються у database. Вони не входять до
frontend bundle, OpenAPI examples, audit або exception messages.

Management command `configure_telegram_webhook`:

1. читає secrets лише з environment/file;
2. викликає `getMe` і перевіряє очікуваний username;
3. встановлює HTTPS webhook;
4. передає `secret_token`;
5. задає `allowed_updates=["message", "callback_query"]`;
6. не використовує `drop_pending_updates=true` без окремої explicit опції.

Telegram API не входить до `/health/ready`: зовнішній outage не повинен робити CRM
unready. Стан webhook/delivery перевіряється окремою operations-командою.

## 9. Авторизація працівника в Telegram

Пароль CRM ніколи не вводиться в боті.

Internal endpoints:

- `GET /telegram/subscription`;
- `POST /telegram/link-intents`;
- `DELETE /telegram/subscription`.

Вони доступні active admin/reception. Frontend додає у profile menu дію
«Підключити Telegram» та personal dialog.

`POST /telegram/link-intents` повертає:

```json
{
  "url": "https://t.me/podo_crm_pod_bot?start=<one-time-payload>",
  "expires_at": "2026-07-28T10:10:00Z"
}
```

Payload має 256-bit entropy, base64url, до 64 символів, у БД зберігається лише
digest. `/start <payload>` приймається лише у private chat, row-lock-ить intent,
повторно перевіряє active role, атомарно створює/оновлює subscription і позначає
intent використаним.

Один Telegram user/chat не може бути підключений до двох CRM users. Повторне
підключення власного акаунта idempotent. `/stop` або CRM disconnect вимикає
subscription. Деактивований користувач чи роль без scope не отримує delivery і
не може виконати callback навіть за наявності старого subscription.

## 10. Telegram webhook

Endpoint:

```text
POST /api/v1/integrations/telegram/webhook
```

Вимоги:

- HTTPS;
- exact constant-time перевірка `X-Telegram-Bot-Api-Secret-Token`;
- no session/CSRF;
- body size limit;
- allowlist update shapes;
- unique `update_id` deduplication;
- повтор webhook повертає `200` без повторної domain mutation;
- webhook лише durable-зберігає update, enqueue-ить processing після commit і
  швидко повертає `200`.

Unknown command/update не виконує domain action. `/start` без чинного payload
пояснює, що підключення потрібно почати з авторизованої CRM. Group/supergroup
chat не може стати subscription.

## 11. Fan-out і callback «Оброблено»

Після commit нової заявки:

1. створюються `TelegramDelivery` для всіх поточних enabled eligible subscriptions;
2. Celery dispatcher викликає `sendMessage`;
3. response `message_id` зберігається у delivery.

Повідомлення — plain text без `parse_mode`, щоб зовнішні значення не ставали
Telegram markup. Воно містить status, public number і source, а також явно
показує optional ім'я, телефон, послугу, handle/message/preferred time та час
створення; відсутні form values позначаються як `Не вказано`.

Inline keyboard:

- `✅ Оброблено` з callback data `br:p:<uuid>` (менше 64 bytes);
- `Відкрити в CRM` з HTTPS deep link `/booking-requests?request=<uuid>`.

Callback processor:

1. викликає `answerCallbackQuery` навіть якщо status уже змінений;
2. перевіряє private chat, active subscription, active CRM user і scope;
3. викликає той самий idempotent domain service, що internal API;
4. перша mutation фіксує CRM user як `processed_by`;
5. unauthorized/unknown callback не розкриває заявку.

Після `PROCESSED` усі `SENT` delivery з
`last_synced_request_version < booking_request.version` отримують
`editMessageText`: status стає `✅ Оброблено`, додається виконавець/час, action
button видаляється, CRM link зберігається.

Synchronization best-effort:

- retry з exponential backoff;
- Telegram flood control поважає `retry_after`;
- deleted/inaccessible message стає `PERMANENT_FAILURE`;
- bot-blocked/forbidden chat вимикає subscription;
- одна failed chat не блокує інші;
- periodic dispatcher підбирає pending/retry/stale delivery;
- application status ніколи не відкочується через transport failure.

## 12. Audit, privacy і logging

Новий `AuditSection.BOOKING_REQUESTS`.

Actions:

- `booking_requests.request_created`;
- `booking_requests.request_processed`;
- `settings.booking_request_token_rotated`;
- `accounts.telegram_subscription_linked`;
- `accounts.telegram_subscription_unlinked`.

Create audit використовує system actor `External integration`. Audit snapshots
не містять phone, message, contact handle, external reference, Bearer token,
Telegram token, webhook secret, chat/user ID або Telegram payload. Дозволені
public number, source, status, version, timestamps і display name виконавця.

Structured logs також не містять PII/credentials; для діагностики дозволені
request/correlation ID, public number, delivery UUID, HTTP status, Telegram
error code та attempt number.

У connect dialog працівник бачить попередження, що контактні дані заявок
надсилатимуться у його private Telegram chat. Group delivery не підтримується.

## 13. Error contract

Зберігається canonical envelope:

```json
{
  "code": "validation_error",
  "message": "Дані запиту не пройшли перевірку.",
  "fields": {},
  "correlation_id": "..."
}
```

Специфічні codes:

- `invalid_bearer_token` — `401`;
- `idempotency_key_required` — `422`;
- `idempotency_payload_mismatch` — `409`;
- `version_conflict` — `409`;
- `telegram_link_expired` — safe bot response, не public API leak;
- `rate_limit_exceeded` — `429`;
- `telegram_unavailable` не повертається зі create/process mutation, бо transport
  асинхронний.

Усі responses external create/token rotation/webhook мають `Cache-Control:
no-store`.

## 14. Обов'язкові gates

Backend:

- model constraints і migration forward→reverse→forward;
- public number uniqueness/concurrency;
- strict serializers, phone normalization, source enum;
- role/route scope та foreign UUID generic `404`;
- process version conflict та repeated/concurrent idempotency;
- token one-time return, digest-only persistence, immediate rotation, concurrent
  rotation і secret redaction;
- external auth, missing/malformed/invalid Bearer, rate limit, idempotency replay,
  payload mismatch і concurrent create;
- Telegram link expiry/one-time/private-chat/unique identity/inactive-role checks;
- webhook secret, duplicate/out-of-order `update_id`, unknown updates;
- fan-out, durable retry, 429 `retry_after`, blocked chat, callback authorization,
  callback race й cross-chat edit synchronization;
- audit rollback і allowlisted snapshots.

Frontend:

- admin/reception route, podologist absence/direct forbidden;
- list/filter/search/cursor/detail/reload deep link;
- process pending/conflict/already-processed states;
- settings generate/rotate/copy-once/clear-secret states;
- personal Telegram connect/disconnect/expired link states;
- keyboard/modal lifecycle, 44px targets, desktop/tablet/mobile, axe.

Contracts/operations:

- OpenAPI snapshot і generated TypeScript schema;
- external Markdown API guide з placeholder-only examples;
- lint, Ruff/format, mypy, Django check/migrations, frontend typecheck/build;
- mocked Bot API tests без real token;
- runtime root/readiness/session smoke;
- production webhook/getMe/send/edit callback smoke лише з новим rotated bot token;
- production evidence ніколи не містить credentials або customer PII.

## 15. Не входить

- пряме читання Instagram/Facebook Graph API;
- browser-side виклик CRM зі статичного сайту;
- chatbot для клієнтів або двостороння переписка;
- Telegram groups/channels;
- attachment/photo intake;
- редагування/видалення/reopen/bulk status;
- auto-create patient/appointment, duplicate merge;
- assignment/SLA/analytics/export;
- per-user delivery preferences;
- SMS/email/Viber/WhatsApp;
- secrets UI для Telegram token;
- гарантія редагування видаленого, заблокованого або недоступного Telegram message.

## 16. Telegram API підстава

- Bot API webhook підтримує `secret_token`, який Telegram повертає у
  `X-Telegram-Bot-Api-Secret-Token`:
  <https://core.telegram.org/bots/api#setwebhook>.
- `update_id` призначений для deduplication/out-of-order recovery:
  <https://core.telegram.org/bots/api#update>.
- Inline callback data має обмеження 1–64 bytes, а callback потрібно завершувати
  через `answerCallbackQuery`:
  <https://core.telegram.org/bots/api#inlinekeyboardbutton>,
  <https://core.telegram.org/bots/api#answercallbackquery>.
- `editMessageText`/`editMessageReplyMarkup` дозволяють best-effort оновити
  раніше надіслану bot message:
  <https://core.telegram.org/bots/api#editmessagetext>,
  <https://core.telegram.org/bots/api#editmessagereplymarkup>.
- Bot deep links передають до 64 base64url-compatible символів у `/start`:
  <https://core.telegram.org/bots/features#deep-linking>.
