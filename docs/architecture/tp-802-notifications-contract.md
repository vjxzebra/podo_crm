# TP-802 — внутрішні сповіщення та ідемпотентні нагадування

Статус контракту: `frozen` 2026-07-22.

## 1. Межа пакета

TP-802 додає recipient-owned внутрішню стрічку CRM, unread state, canonical deep
links і часові нагадування Celery beat. PostgreSQL є єдиним сховищем стану;
Redis/Celery не зберігають бізнес-факти й не виконують domain mutations.

Не входять: SMS, email, месенджери, browser push, довільні шаблони, user-defined
notification settings, export і видалення історії.

## 2. Модель та інваріанти

`Notification` зберігає UUID, recipient, kind, stable `event_key`, title, message,
tone, important flag, canonical relative `deep_link`, event/created time та nullable
`read_at`.

- unique `(recipient, event_key)` гарантує один результат для retry/concurrency;
- content створюється лише server-side; `event_key`, source metadata та recipient ID
  не серіалізуються;
- `deep_link` завжди локальний (`/...`, але не `//...`) і route-доступний recipient;
  невідомий або недоступний target деградує до `/`;
- read mutation змінює лише `read_at`; повтор не змінює timestamp;
- list/detail mutation завжди починаються з `recipient=actor`, тому чужий UUID дає
  однаковий `404` без витоку існування;
- inactive users не отримують нові notifications.

## 3. API

### `GET /api/v1/notifications?status=&cursor=`

- authentication required;
- `status`: `all` (default) або `unread`;
- cursor pagination, newest first, page size 30;
- response: `notifications`, `total_count`, `unread_count`, `next_cursor`;
- item: `id`, `kind`, `title`, `message`, `tone`, `is_important`, `deep_link`,
  `occurred_at`, `created_at`, `read_at`, `is_read`.

Counts обчислюються в recipient scope до status filter/pagination.

### `POST /api/v1/notifications/{id}/read`

Порожній strict body. Ідемпотентно встановлює `read_at`; повтор повертає той самий
timestamp. Чужий або невідомий UUID — `404`.

### `POST /api/v1/notifications/read-all`

Порожній strict body. Одним update позначає прочитаними всі поточні unread rows
recipient і повертає `marked_count`, `unread_count=0`; повтор повертає `0`.

## 4. Джерела подій

Immediate notifications створюються через `transaction.on_commit()` і не можуть
зламати вже committed domain mutation:

- `appointment_arrived` → assigned active podologist;
- `appointment_canceled` → assigned active podologist;
- `visit_payment_ready` → active reception/admin, лише для non-zero OPEN
  receivable з payment handoff;
- `password_reset_requested` → active admins.

Payload складається з безпечних snapshots: номер/ім’я пацієнта, послуга, час,
сума або працівник. Clinical notes, complaints, фото, credentials, signed URLs,
supplier/purchase cost і finance facts для podologist не передаються.

## 5. Часові нагадування

Celery beat щохвилини запускає один task, який:

- створює `appointment_upcoming` assigned podologist для active appointment, що
  починається у контрольному 15-хвилинному вікні;
- створює `work_item_overdue` active assignee для відкритої простроченої справи.

Event key містить canonical object ID та scheduled timestamp. Повтор task,
concurrent workers або retry не створюють duplicate. Reschedule/due-time change
формують новий ключ; completed/canceled/inactive objects відсікаються до create.

## 6. UI і deep links

`/notifications` замінює preview на responsive центр сповіщень:

- loading/error/retry, all/unread filters, grouped list, empty states;
- server-derived unread badge у topbar; badge синхронізується після read/read-all;
- `Позначити всі прочитаними` і відкриття item мають pending/error recovery;
- відкриття item спершу ідемпотентно читає його, потім переходить на canonical
  patient/calendar/finance/inventory/work-item/password-reset route;
- unsafe/unsupported link має frontend fallback `/` навіть попри server guarantee;
- desktop/tablet/mobile: no page overflow, controls щонайменше 44 px, keyboard
  focus visible; mobile лишається звичайною route page, а не вкладеним modal.

Canonical targets:

- appointment: `/calendar?appointment={uuid}`;
- payment handoff: `/finance?operation=PAYMENT:{receivable_uuid}`;
- overdue work item: `/work-items?item={uuid}`;
- password reset: `/password-resets`;
- safe fallback: `/`.

## 7. Обов'язкові gates

- model/DB constraints, repeated/concurrent create, repeated read/read-all;
- admin/reception/podologist recipient scope, inactive recipient skip, foreign UUID
  `404`, response-key redaction і safe-link fallback;
- duplicate Celery task, appointment/reschedule/canceled/work-item filters;
- on-commit integration для appointment, finish і password-reset events;
- OpenAPI snapshot/generated TypeScript types, lint/typecheck/build;
- migration forward→reverse→forward із data-preservation snapshot;
- authenticated desktop/tablet/mobile browser evidence та clean console.
