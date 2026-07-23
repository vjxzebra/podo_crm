# TP-803 — admin audit list/detail «Було → Стало»

Статус контракту: `frozen` 2026-07-22.

## 1. Межа пакета

TP-803 доводить TP-207 append-only audit foundation до production admin UI. PostgreSQL
`AuditEvent` лишається єдиним джерелом фактів, а frontend є лише read-only
проєкцією redacted snapshots.

Не входять: create/update/delete audit events, export, retention controls, restore,
довільні saved filters, non-admin access і новий business-event store.

## 2. Доступ та незмінність

- `/audit` і обидва API endpoints доступні тільки active admin;
- reception/podologist не отримують route ID, а direct API повертає `403`;
- anonymous API повертає `401`;
- detail ніколи не має edit/delete/export actions;
- model/queryset/database trigger продовжують забороняти update/delete;
- actor та object labels є historical snapshots і не змінюються після rename або
  deactivation linked records.

## 3. API

### `GET /api/v1/audit-events`

Query:

- `search` — actor name/email, action, object type/ID/label або description;
- `actor_id` — один historical/current працівник;
- `section` — registered `AuditSection`;
- `date_from`, `date_to` — inclusive ISO timestamps, `date_from ≤ date_to`;
- `cursor` — UUID останнього row попередньої сторінки.

Відповідь: newest-first `events` і nullable `next_cursor`, page size 50. Item містить
UUID/time, historical actor snapshot, section/action, stable object
`type/id/label`, result і description. Invalid filter — shared `422`; невідомий
cursor — `404`.

### `GET /api/v1/audit-events/{event_id}`

Повертає list fields плюс redacted `before`, `after`, sorted top-level `changes`,
service note і correlation ID. Невідомий UUID — `404`.

Admin UI використовує наявний `GET /api/v1/users?status=all` лише для employee
filter options; audit events не залежать від поточного active state працівника.

## 4. Redaction і registry coverage

- passwords, hashes, tokens, session/cookie/authorization values, credentials,
  access/secret keys і signed URLs редагуються рекурсивно до persistence;
- password lifecycle metadata на кшталт `must_change_password` та expiry лишається
  дозволеним;
- однакові redacted before/after values не створюють оманливий change row;
- кожен `AuditAction` повинен мати рівно одну `EVENT_SECTIONS` registration;
- registry покриває мінімум SPEC §14.1: appointment, patient/medical, visit finish,
  payment/refund/cash/shift, inventory/stocktake, team/password і settings families.

## 5. UI

`/audit` має:

- admin-only navigation item і owner/read-only badge;
- search submit, employee/section/date filters, clear та refresh;
- loading skeleton, initial empty, filtered empty, list error/retry і cursor load-more;
- newest-first responsive list/table з time, actor+role, section, action, object і
  result;
- click/keyboard selection відкриває detail через canonical `/audit?event={uuid}`;
- reload/back зберігає selected event; close очищає лише `event` query parameter і
  повертає focus на origin row;
- detail має identity, full timestamp, actor, object, description, усі changed
  fields як cards «Було → Стало», note/correlation context і immutable marker;
- empty `changes` показує explicit «Змінені поля не зафіксовані», не raw secrets;
- detail loading/error/retry не руйнує list/filter state.

Desktop/tablet використовують list + sticky detail panel; mobile detail є
fullscreen modal route state з focus trap, `Escape`, body lock і focus return.
Page не має horizontal overflow, interactive controls — щонайменше 44 px.

## 6. Presentation rules

- section/action/field codes мають українські labels із safe code fallback;
- JSON scalar/array/object values форматуються читабельно; `null`, empty string,
  empty collection і redacted value відрізняються візуально;
- frontend не будує object URL із довільного server string;
- optional «Відкрити об’єкт» дозволений лише для явного allowlist canonical routes;
- audit event deep link є stable UUID, а не row index або timestamp.

## 7. Обов'язкові gates

- registry completeness, redaction, immutability, filters/range/cursor, historical
  actor snapshot, admin/reception/podologist/anonymous API tests;
- route visibility/direct-route guard, list/detail/deep-link/reload/close, all
  loading/empty/error/retry/filter/cursor states та value formatting tests;
- OpenAPI snapshot/generated TypeScript types, lint/typecheck/build і axe;
- `makemigrations --check`, existing migration/runtime/data preservation;
- authenticated desktop/tablet/mobile browser evidence, focus/overflow metrics і
  clean console.
