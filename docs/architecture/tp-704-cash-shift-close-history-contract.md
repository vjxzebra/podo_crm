# TP-704: контракт закриття, звірки та історії касових змін

- Стан реалізації: `done` 2026-07-22; backend/frontend/contracts/migration,
  runtime та authenticated read-only browser gates пройшли
- Джерела: SPEC §10.1–10.5, AC-16—AC-17, ADR-006,
  `docs/architecture/domain-model.md`
- Залежність: TP-701—TP-703
- Межа пакета: strict close/reconciliation власної відкритої зміни або admin
  override, role-scoped history і immutable detail

Цей документ заморожує API, concurrency, RBAC та UI-межу TP-704. Фізична
готівка не дорівнює загальному виторгу: `expected` і `actual` у reconciliation
стосуються лише cash ledger.

## 1. Read model касової зміни

`CashShiftProjection` є повною immutable detail projection:

```json
{
  "id": "shift-uuid",
  "public_number": "CSH-...",
  "status": "CLOSED",
  "employee": {
    "id": 11,
    "name": "Працівник",
    "email": "employee@example.test",
    "role": "reception"
  },
  "opened_at": "2026-07-22T07:00:00Z",
  "closed_at": "2026-07-22T16:00:00Z",
  "totals": {},
  "reconciliation": {
    "expected_cash_minor": 125000,
    "actual_cash_minor": 124500,
    "discrepancy_minor": -500,
    "comment": "Нестача підтверджена перерахунком",
    "closed_by": {
      "id": 11,
      "name": "Працівник",
      "email": "employee@example.test",
      "role": "reception"
    }
  },
  "entries": []
}
```

Для `OPEN` поля `closed_at` і `reconciliation` дорівнюють `null`. Для
`CLOSED` обидва non-null. `totals` лишається ledger-derived shape TP-701:
operations/payment/refund counts, payment/refund totals, method breakdown,
deposits, withdrawals, revenue та expected cash. Entries повертаються
newest-first і містять усі фактичні rows вибраної зміни; unpaid Receivable без
ledger entry не входить до detail.

Employee, closer та operation actor labels є snapshots відповідного моменту,
а не поточними mutable профілями. History list використовує
`CashShiftSummary`: той самий shape без `entries`.

## 2. Close preview

`GET /api/v1/cash-shifts/{shift_id}/close-preview` повертає authoritative
дані без mutation:

```json
{
  "shift": {"id": "shift-uuid", "status": "OPEN", "totals": {}},
  "unpaid": {"count": 2, "total_minor": 180000}
}
```

`shift` — повний `CashShiftProjection`. `unpaid` є clinic-wide aggregate
positive `Receivable.status=OPEN`; він показується warning, не входить у
ledger і не блокує close. Endpoint доступний власнику OPEN shift та admin.
Reception для чужого/unknown UUID отримує однаковий `404 not_found`.

Preview не є lock або reservation. Його ledger preconditions передаються у
close request і повторно перевіряються під row lock.

## 3. Закриття та reconciliation

`POST /api/v1/cash-shifts/{shift_id}/close` потребує trimmed non-empty
`Idempotency-Key`, max 128. Strict request (`additionalProperties: false`):

```json
{
  "actual_cash_minor": 124500,
  "expected_operations_count": 7,
  "cash_count_confirmed": true,
  "comment": "Нестача підтверджена перерахунком"
}
```

Правила:

- `actual_cash_minor`: integer `0..9007199254740991`;
- `expected_operations_count`: integer `0..2147483647`;
- `cash_count_confirmed` приймає лише literal `true`; omitted/false — `422`;
- `comment`: optional, trim, max 2000, default `""`;
- expected cash завжди повторно обчислює сервер; client-supplied expected cash
  та discrepancy заборонені;
- `discrepancy_minor = actual_cash_minor - authoritative expected cash`;
- non-zero discrepancy потребує non-empty comment;
- amount, actor, shift status, closed time і discrepancy не приймаються з
  клієнтського body під іншими полями.

Service в одній transaction:

1. перевіряє exact idempotent replay;
2. lock-ить CashShift `FOR UPDATE`;
3. повторно перевіряє owner/admin scope і `OPEN`;
4. рахує authoritative totals із ledger;
5. порівнює `expected_operations_count` з authoritative ledger count;
6. при збігу зберігає expected/actual/discrepancy/comment, closer snapshots і
   close idempotency metadata;
7. переводить shift у `CLOSED` та пише `cash.shift_closed` audit у тій самій
   transaction.

Якщо будь-який ledger row з'явився після preview, operations count зміниться
навіть для card/transfer operation. Service повертає `409 cash_shift_changed`;
клієнт повторно завантажує preview, зберігає actual/comment, скидає counted
confirmation, перераховує discrepancy й вимагає нове підтвердження.

Нова mutation повертає `201`, exact replay — `200`:

```json
{"shift": {"id": "shift-uuid", "status": "CLOSED"}, "replayed": false}
```

Exact key + normalized payload повертає той самий immutable snapshot із
`replayed=true`, навіть коли shift уже CLOSED. Той самий actor/key з іншим
payload повертає `409 idempotency_payload_mismatch`. Інший key для CLOSED
shift повертає `409 cash_shift_already_closed`.

Reception може закрити лише власну shift. Admin може закрити будь-яку OPEN
shift, але `closed_by` та audit зберігають фактичного admin actor. Podologist
отримує `403` до object lookup.

## 4. Історія та detail API

### 4.1. List

`GET /api/v1/cash-shifts` має параметри:

| Поле | Правило |
|---|---|
| `search` | optional trimmed string max 255; shift number, employee snapshot name/email |
| `date_from`, `date_to` | optional ISO date, inclusive за `opened_at` у `Europe/Kyiv`; reverse range — `422` |
| `status` | optional `OPEN\|CLOSED` |
| `employee_id` | optional positive integer, лише admin |
| `cursor` | optional opaque string |

Reception завжди отримує лише власні shifts і не може розширити scope query
parameter-ом. Admin бачить усі та може фільтрувати employee. Podologist —
`403`. Order/cursor: `opened_at DESC, id DESC`; page size 40.

Response:

```json
{"shifts": [], "next_cursor": null}
```

Кожен row є `CashShiftSummary`; totals рахуються по повному ledger цієї shift,
а не по поточній сторінці entries. Export і fake period totals не входять до
TP-704.

### 4.2. Detail

`GET /api/v1/cash-shifts/{shift_id}` повертає повний
`CashShiftProjection` з усіма ledger entries newest-first. Reception читає
лише власні shifts; foreign/unknown UUID не розрізняються (`404`). Admin читає
будь-яку. Closed detail ніколи не має edit/delete/reopen controls.

## 5. Stable errors та database invariants

Canonical errors:

- `409 cash_shift_changed`;
- `409 cash_shift_already_closed`;
- `409 idempotency_payload_mismatch`;
- `409 idempotency_key_conflict` для неконсистентного persisted result;
- `422 idempotency_key_required` / `idempotency_key_invalid`;
- shared `401 authentication_required`, `403 permission_denied`,
  `404 not_found`, `422 validation_error`.

Validation, stale precondition, permission error або audit failure не змінюють
shift і не залишають partial audit/idempotency state.

Migration посилює CashShift lifecycle:

- OPEN має null close fields, порожні closer/idempotency metadata;
- CLOSED має non-null close fields, closer та non-empty key/hash/snapshots;
- `discrepancy = actual - expected`;
- non-zero discrepancy має trimmed non-empty comment;
- lifecycle trigger на OPEN → CLOSED перевіряє ledger-derived expected cash;
- CLOSED immutable, no reopen/delete;
- ledger insert trigger продовжує lock-ити shift та відхиляє entry до CLOSED;
- exact close key унікальний у close-idempotency family actor;
- reverse migration відхиляється, якщо вже є CLOSED rows і downgrade втратив
  би TP-704 metadata.

Existing OPEN rows отримують employee snapshots без зміни ledger або status.
Якщо preflight знаходить legacy CLOSED row без достовірного closer/key, forward
migration abort-иться з actionable error замість вигаданого backfill.

## 6. UI state machine

Finance navigation має URL-backed views:

- `/finance` — поточна зміна й фінансові операції;
- `/finance/shifts` — history.

Reception бачить власну history; admin — усю history та employee filter. У
close dialog actual початково порожній, checkbox unchecked, submit disabled.
Actual допускає `0` і дві десяткові цифри. Live state:

- `0` — «Каса зійшлася»;
- positive — «Надлишок +X»;
- negative — «Нестача −X».

Зміна actual скидає confirmation. Non-zero discrepancy робить comment
required. Dirty close через Escape/backdrop/X/Cancel потребує discard confirm;
pending submit блокує всі close paths і double submit.

Після ambiguous network failure exact body/key заморожені, доступний лише retry
того самого request. Після definite `cash_shift_changed` actual/comment
зберігаються, preview оновлюється, confirmation скидається. Success refresh-ить
current shift, operations і history та переходить до authoritative closed row.

History підтримує день, місяць і довільний inclusive period. Desktop має
semantic table, mobile — semantic cards. Row містить date/number, employee,
open/close times, revenue, cash/card, expected/actual, discrepancy і status та
окрему кнопку detail. Detail dialog показує всі totals, reconciliation,
close comment/closer і повний ledger; для OPEN actual/discrepancy — «—».

Dialogs мають focus trap/return, body scroll lock, phone fullscreen layout,
native checkbox, `aria-live` discrepancy, invalid descriptions і targets не
менші 44 px. Export control відсутній (GAP-18).

## 7. Acceptance gates

- balanced zero/non-zero cash close; excess і shortage comment validation;
- owner/admin/foreign reception/podologist RBAC;
- exact replay, payload mismatch, double/concurrent close;
- close/payment, close/refund і close/cash-adjustment race;
- stale preview response, refresh та re-confirm UX;
- ledger formula, DB raw-SQL lifecycle/formula/comment/closed-insert guards;
- audit failure rollback і immutable user/actor snapshots;
- own-only/admin list, filters, clinic-local dates, cursor stability;
- full detail/empty ledger/foreign-safe not-found;
- strict OpenAPI/generated client and negative unknown-field schemas;
- component tests, axe, production build, migration forward/reverse gates;
- read-only runtime/browser verification without closing user-owned dev shift.

## 8. Поточний verification status

Автоматизовані та локальні інтеграційні gates пройшли: 298 backend, 164
frontend і 35 axe tests; focused billing suite — 71 test, з них 14 покривають
TP-704 API та migration. OpenAPI snapshot, generated TypeScript schema,
lint/typecheck і production build синхронні. Dev migration
`0004 → 0005 → 0004 → 0005` зберегла одну OPEN shift і єдину CARD-операцію,
а runtime `/`, `/finance`, `/finance/shifts` і `/health/ready` повертає `200`.

Повний журнал доказів: [TP-704 evidence](../evidence/tp-704/README.md).
Authenticated browser gate перевірив desktop history/detail/close dialog без
submit, responsive cards на `768×1024` і `390×844`, відсутність page overflow,
44 px targets і чисту console. Пакет має стан `done`, AC-16—AC-17 —
`verified`. Live close user-owned dev shift не виконувався; фінальний DB
snapshot підтвердив незмінний OPEN стан.

## 9. Не входить до TP-704

- reopen/edit/delete closed shift або ledger entry;
- correction of a closed reconciliation; окремий compensating workflow;
- export, accounting reports, bank/acquiring settlement;
- opening balance, multi-currency, cash drawer hardware;
- closing several shifts in one request or scheduled automatic close.
