# План реалізації заявок та Telegram-бота

Дата: 2026-07-28.

Authoritative contract:
[TP-1008—TP-1011](../architecture/tp-1008-1011-booking-requests-telegram-contract.md).

## 1. Порядок робіт

```text
TP-1008 CRM-реєстр заявок
    ↓
TP-1009 Bearer API, token rotation і документація
    ↓
TP-1010 Telegram authorization та fan-out
    ↓
TP-1011 callback, cross-chat sync і production gate
```

Кожен packet завершується окремою перевірюваною вертикаллю і не покладається на
незбережений transport state.

## 2. TP-1008 — домен і розділ «Заявки»

Статус: `done` 2026-07-28.

### Результат

Admin/reception бачать новий role-scoped розділ `/booking-requests`, можуть
переглянути отримані fixture/service-created заявки і idempotently позначити
заявку обробленою. Podologist не бачить route та отримує backend `403`.

### Backend

1. Створити `apps.booking_requests` і migration.
2. Додати `BookingRequest`, immutable public number, constraints/indexes.
3. Додати `AccessScope.BOOKING_REQUESTS`, permissions і route ids.
4. Реалізувати role-scoped cursor selectors.
5. Реалізувати internal list/detail/process API.
6. Реалізувати row-lock process service з optimistic version та repeated
   processed semantics.
7. Додати audit section/actions, safe snapshots і frontend presentation registry.
8. Додати test/demo factory без production customer data.

### Frontend

1. Додати route/navigation/icon та API client module.
2. Реалізувати summary, status/source filters, search і load-more.
3. Реалізувати desktop table і mobile cards.
4. Реалізувати reload-stable detail `?request=<uuid>`.
5. Реалізувати process pending/success/conflict/already-processed states.
6. Додати component/a11y/responsive coverage.

### Definition of done

- migration forward/reverse/reapply green;
- model/service/API RBAC/concurrency/audit tests green;
- OpenAPI snapshot і generated TypeScript schema актуальні;
- frontend component, axe, lint, typecheck і build green;
- authenticated admin/reception/podologist browser gate на desktop/tablet/mobile;
- runtime `/health/ready` `200`;
- жодного external Bearer/Telegram endpoint у цьому packet.

### Не входить

External create, token settings, Telegram, manual CRM create, edit/delete,
patient/appointment conversion.

## 3. TP-1009 — Bearer API, token rotation і integration guide

Статус: `done` 2026-07-28.

### Результат

Admin генерує/ротатує request API token у `/settings`, копіює його один раз, а
server-side Instagram/Facebook/site integration idempotently створює `NEW`
заявку через documented Bearer API.

### Backend

1. Додати `BookingRequestApiCredential` singleton і
   `BookingRequestSubmission`.
2. Реалізувати digest-only token generation/rotation, row lock, version і audit.
3. Реалізувати custom Bearer authentication/OpenAPI scheme.
4. Реалізувати strict external serializer, phone normalization і minimal response.
5. Реалізувати `Idempotency-Key`, canonical payload hash та concurrent replay.
6. Додати valid-token та invalid-IP Redis rate limit.
7. Додати no-store/redaction/logging regressions.

### Frontend і документація

1. Додати admin-only вкладку settings «Інтеграції».
2. Реалізувати first generate, rotate confirmation, copy-once і clear-on-close.
3. Фіналізувати
   [integration guide](../integrations/booking-requests-api.md).
4. Додати OpenAPI examples із placeholder token.

### Definition of done

- token plaintext відсутній у database, audit, logs, snapshots і frontend після
  закриття dialog;
- старий token одразу повертає `401` після rotation;
- initial create/replay/mismatch/concurrent create/rate limit gates green;
- документація перевірена реальним локальним HTTP викликом із локальним
  Git-ignored token;
- canonical backend/frontend/contracts/build gates green.

### Не входить

Bot token у settings, browser-side secret, OAuth/multiple credentials, Telegram.

## 4. TP-1010 — Telegram authorization та доставка нових заявок

Статус: `done` 2026-07-28.

### Результат

Active admin/reception без передачі пароля підключає private Telegram chat через
one-time deep link. Кожна нова заявка durable доставляється всім enabled eligible
subscriptions.

### Backend/operations

1. Додати link intent, subscription, update inbox і delivery outbox models.
2. Додати personal subscription/link/disconnect internal API.
3. Додати profile dialog у desktop/mobile shell.
4. Реалізувати Bot API client з timeouts, sanitized errors і fake transport tests.
5. Реалізувати webhook secret validation/update dedupe.
6. Реалізувати `/start <one-time-payload>` і `/stop`.
7. Реалізувати send dispatcher, stored `message_id`, retry/backoff/periodic pickup.
8. Додати env/file-secret contract та management command для webhook setup.

### Definition of done

- one-time/expiry/private-chat/unique-identity/role-change gates green;
- new request створює рівно одну delivery на eligible subscription;
- broker enqueue failure не губить pending delivery;
- 429 retry та blocked-chat disable перевірені fake Bot API;
- secrets відсутні у tracked files і test output;
- local contract gates працюють без real Telegram token.

### Не входить

Process callback, cross-chat edit, group chats, production enablement.

## 5. TP-1011 — process callback, cross-chat sync і release gate

Статус: `done` 2026-07-28.

### Результат

Inline-кнопка `✅ Оброблено` викликає той самий domain service, status одразу
змінюється в CRM, а всі sent messages best-effort переходять у processed
projection. Зміна status у CRM запускає ту саму синхронізацію.

### Backend

1. Додати compact callback parser і active-subscription authorization.
2. Викликати `answerCallbackQuery` для success/already/forbidden result.
3. Покрити concurrent CRM-vs-Telegram і Telegram-vs-Telegram race.
4. Реалізувати `editMessageText` для всіх stale deliveries.
5. Видалити action button, зберегти CRM deep link.
6. Реалізувати retry/429/permanent message failure isolation.
7. Додати operations status/retry command.

### Production rollout

1. Відкликати раніше оприлюднений bot token через BotFather.
2. Створити новий bot token і окремий webhook secret.
3. Записати їх лише у production secret files/environment.
4. Deploy backward-compatible migration/code.
5. Виконати `getMe`, перевірити username, встановити webhook із secret header.
6. Підключити тестових admin/reception через one-time CRM links.
7. Створити synthetic заявку без реальних customer data.
8. Перевірити fan-out, callback, CRM status і edit у всіх тестових чатах.
9. Очистити synthetic data, але зберегти redacted evidence.

### Definition of done

- webhook replay не дублює mutation;
- unauthorized callback не розкриває заявку;
- перший actor/time не змінюються повторним callback;
- усі доступні sent copies оновлюються, failed copies не блокують domain;
- full backend/frontend/OpenAPI/migration/runtime/security gates green;
- production evidence не містить token, chat id, phone, message або customer PII.

## 6. Ризики та запобіжники

| Ризик | Запобіжник |
|---|---|
| Bearer token витік у browser | лише server-to-server, copy-once, digest-only storage |
| Bot token уже оприлюднений | обов'язкова rotation до production rollout |
| Duplicate webhook/API retry | unique update id та Idempotency-Key + payload hash |
| Двоє одночасно обробляють | row lock, idempotent terminal status, один audit actor |
| Telegram недоступний | durable delivery outbox, retry, CRM mutation не відкочується |
| Message видалено/бот заблоковано | permanent failure/disable лише exact subscription |
| Telegram identity підмінено | one-time deep link, private chat, unique Telegram user/chat |
| Працівника деактивовано | eligibility recheck перед кожною delivery/callback |
| PII або secrets у logs | allowlisted logging/audit, redaction regression tests |
| Масова ротація request token ламає інтеграцію | confirm warning, hint/timestamp, documented rollout |

## 7. Готовність

TP-1008 і TP-1009 завершені. Bearer token lifecycle, зовнішній idempotent API,
OpenAPI, integration guide та admin settings перевірені автоматично, живим
локальним HTTP викликом і responsive browser gate.

TP-1010 завершено локально без реального Telegram token: one-time private
authorization, verified webhook і durable fan-out покриті fake Bot API gates та
живим CRM dialog browser gate.

TP-1011 завершено локально без реального Telegram token: authorized inline
callback, first-actor idempotency, cross-chat edit synchronization,
retry/permanent-failure isolation і production rollout runbook покриті fake Bot
API та runtime gates.

Наступний етап — production rollout за
[Telegram runbook](../operations/telegram-rollout-runbook.md) тільки після
rotation скомпрометованого bot token.
