# TP-703: контракт повного повернення та cash adjustments

- Стан реалізації: `done` 2026-07-22; [evidence TP-703](../evidence/tp-703/README.md)
- Джерела: SPEC §9.4–9.7, AC-14—AC-15, ADR-003, ADR-006,
  `docs/architecture/domain-model.md`
- Залежність: [заморожений контракт TP-702](tp-702-finance-contract.md)
- Межа пакета: одне повне повернення проведеної оплати та службове
  внесення/вилучення готівки у власній відкритій касовій зміні

Цей документ є реалізованим і перевіреним frozen contract API, projection,
concurrency та UI-межі TP-703. TP-703 розширює TP-702 additively: стабільний
`PAYMENT` row на `Receivable` не замінюється ledger-only моделлю.

## 1. Розширення списку фінансових операцій

`GET /api/v1/finance/operations` повертає tagged union із трьох read models:

1. `PAYMENT` — рівно один стабільний row на `Receivable`, як у TP-702;
2. `REFUND` — окремий immutable row фактично проведеного повернення;
3. `DEPOSIT` або `WITHDRAWAL` — окремий immutable cash-adjustment row.

Окремий `REFUND` row зберігає час, actor і касову зміну повернення та робить
фільтр `type=REFUND` змістовним. Початковий `PAYMENT` row при цьому не
пересувається в хронології: його `occurred_at` лишається часом початкової
оплати, а status переходить `PAID → REFUNDED`.

### 1.1. Query parameters

| Поле | Тип і правило |
|---|---|
| `search` | optional string, max 255; patient name/phone/number, visit/payment/refund/cash-operation number, snapshot service code/name, cash-adjustment reason/comment |
| `type` | optional enum `PAYMENT\|REFUND\|DEPOSIT\|WITHDRAWAL` |
| `status` | optional enum `OPEN\|PAID\|REFUNDED\|POSTED` |
| `date_from`, `date_to` | optional ISO date, inclusive у `Europe/Kyiv`; зворотний діапазон — `422` |
| `payment_method` | optional enum `CASH\|CARD\|TRANSFER`; збігається з actual Payment та inherited Refund, cash adjustments не збігаються |
| `patient_id` | optional UUID; звужує лише `PAYMENT` і `REFUND` rows |
| `amount_minor` | optional integer `0..9007199254740991`; exact amount match, включно з zero-settled receivables |
| `refundable_only` | optional boolean; повертає лише positive actual `PAYMENT` у status `PAID`, без попереднього Refund |
| `cursor` | optional opaque string |

`refundable_only=true` сумісний лише з omitted/`PAYMENT` type та
omitted/`PAID` status; несумісна комбінація повертає `422 validation_error`.
Він виключає zero-settled `PAID` receivables із `payment=null` і є canonical
query refund picker. Значення-сентінел `"all"` не є частиною API enum і
відхиляється як `422`.

Page size лишається 40. Глобальний stable order і cursor tuple:

```text
occurred_at DESC, id DESC, type DESC
```

Для `PAYMENT` час має семантику TP-702: visit completion для `OPEN` і
zero-settled row, original payment time для `PAID`/`REFUNDED`. Для `REFUND`,
`DEPOSIT` і `WITHDRAWAL` це immutable ledger `posted_at`.

### 1.2. PAYMENT variant

TP-702 shape зберігається та отримує одне required nullable поле `refund`:

```json
{
  "id": "receivable-uuid",
  "type": "PAYMENT",
  "status": "REFUNDED",
  "occurred_at": "2026-07-21T09:12:00Z",
  "amount_minor": 85000,
  "patient": {
    "id": "patient-uuid",
    "public_number": "PAT-...",
    "display_name": "Ім'я Прізвище",
    "phone": "+380..."
  },
  "visit": {
    "id": "visit-uuid",
    "public_number": "V-...",
    "completed_at": "2026-07-21T08:55:00Z",
    "payment_handoff_requested": true,
    "total_minor": 85000,
    "specialist": {"id": 7, "name": "Ім'я Прізвище"},
    "services": []
  },
  "payment": {
    "id": "payment-uuid",
    "ledger_entry_id": "payment-ledger-uuid",
    "public_number": "TXN-...",
    "payment_method": "CARD",
    "comment": "",
    "posted_at": "2026-07-21T09:12:00Z",
    "actor": {"id": 11, "name": "Працівник"},
    "cash_shift": {"id": "original-shift-uuid", "public_number": "CSH-..."}
  },
  "refund": {
    "id": "refund-uuid",
    "ledger_entry_id": "refund-ledger-uuid",
    "public_number": "TXN-...",
    "reason": "Причина повернення",
    "posted_at": "2026-07-22T10:30:00Z",
    "actor": {"id": 15, "name": "Інший працівник"},
    "cash_shift": {"id": "current-shift-uuid", "public_number": "CSH-..."}
  }
}
```

Nullability/state invariants:

- `OPEN`: `payment=null`, `refund=null`;
- positive `PAID`: `payment` non-null, `refund=null`;
- `REFUNDED`: `payment` і `refund` non-null;
- zero-settled `PAID`: `payment=null`, `refund=null`, refund action відсутня.

Patient, visit, specialist, services і original actor для paid/refunded rows
походять з immutable Payment snapshots. Refund actor name також є snapshot,
а не поточним mutable display name працівника.

### 1.3. REFUND variant

Окремий tagged row використовує Refund UUID як `id`, `type=REFUND`,
`status=POSTED`, refund ledger time як `occurred_at` і додатний
`amount_minor`. Він містить:

- `patient` і `visit` у тому самому safe snapshot shape, що `PAYMENT`;
- required `original_payment` у TP-702 Payment shape;
- required `refund` у shape з розділу 1.2.

Refund detail тому показує original payment, patient, visit/services, inherited
method, reason, обидві касові зміни та обох actors без читання mutable source
fields. Медичні нотатки, огляд, фото й рекомендації не серіалізуються.

### 1.4. Cash-adjustment variant

`DEPOSIT` і `WITHDRAWAL` rows використовують CashAdjustment UUID як `id`,
`status=POSTED`, ledger time як `occurred_at` і додатний `amount_minor`:

```json
{
  "id": "cash-adjustment-uuid",
  "type": "WITHDRAWAL",
  "status": "POSTED",
  "occurred_at": "2026-07-22T11:00:00Z",
  "amount_minor": 50000,
  "cash_adjustment": {
    "id": "cash-adjustment-uuid",
    "ledger_entry_id": "ledger-uuid",
    "public_number": "TXN-...",
    "reason": "Інкасація",
    "comment": "",
    "posted_at": "2026-07-22T11:00:00Z",
    "actor": {"id": 15, "name": "Працівник"},
    "cash_shift": {"id": "shift-uuid", "public_number": "CSH-..."}
  }
}
```

Цей variant фізично не містить `patient`, `visit`, `payment_method`,
`payment` або `refund` keys. OpenAPI описує operation response як `oneOf` із
required literal discriminator `type`, а generated TypeScript client має
звужувати union без casts.

Amounts у БД та API завжди додатні; напрямок визначає `type`. UI показує
`PAYMENT`/`DEPOSIT` як надходження, `REFUND`/`WITHDRAWAL` як видаток, а
`OPEN PAYMENT` — як нейтральну заборгованість. Знак не входить до request і не
зберігається в `amount_minor`.

## 2. Проведення повного повернення

`POST /api/v1/payments/{payment_id}/refunds` потребує header
`Idempotency-Key`: trimmed non-empty string, max 128.

Strict request із `additionalProperties: false`:

```json
{"reason": "Причина повернення"}
```

- `reason` required, trim, non-empty, max 500;
- `amount_minor`, `payment_method`, `comment`, patient/visit/receivable,
  cash shift, actor і status не приймаються;
- сума сервером копіюється з original Payment ledger і дорівнює повній сумі
  Receivable;
- method сервером копіюється без змін із original Payment;
- один Payment має не більше одного Refund.

Refund eligible лише коли існує positive actual Payment, Receivable має status
`PAID`, previous Refund відсутній, а actor має власну `OPEN` shift. Zero-settled
receivable без Payment повернути неможливо.

Original Payment може належати іншому працівнику та іншій, у тому числі вже
закритій, cash shift. Refund завжди додається до власної поточної OPEN shift
actor; original ledger і original shift не змінюються. Для inherited `CASH`
потрібно, щоб expected physical cash поточної target shift була не меншою за
повну суму refund. Для `CARD` і `TRANSFER` physical-cash guard не застосовується.

Нова mutation повертає `201`, exact replay — `200`:

```json
{"operation": {"id": "refund-uuid", "type": "REFUND"}, "replayed": false}
```

`operation` є повним `REFUND` variant із розділу 1.3.

## 3. Внесення й вилучення готівки

`POST /api/v1/cash-movements` потребує той самий `Idempotency-Key` contract.

Strict request із `additionalProperties: false`:

```json
{
  "type": "DEPOSIT",
  "amount_minor": 50000,
  "reason": "Розмінні кошти",
  "comment": ""
}
```

- `type` required enum `DEPOSIT|WITHDRAWAL`; API codes лише uppercase;
- `amount_minor` required integer `1..9007199254740991`
  (`Number.MAX_SAFE_INTEGER` у minor units);
- `reason` required, trim, non-empty, max 500;
- `comment` optional, trim, max 2000, default `""`;
- patient, visit, payment/receivable, `payment_method`, cash shift, actor,
  status і signed amount не приймаються.

Reasons є вільним текстом; prototype presets не є закритим API enum.
`DEPOSIT` збільшує expected cash. `WITHDRAWAL` зменшує її й дозволений, якщо
amount дорівнює доступній готівці, але не перевищує її. Обидва kinds завжди є
cash adjustments і зберігають ledger `payment_method=""`.

Нова mutation повертає `201`, exact replay — `200`; response
`{operation, replayed}` використовує повний cash-adjustment variant.

## 4. RBAC, idempotency та stable errors

Admin і reception читають clinic-wide safe projection та можуть проводити
refund/cash adjustment лише у власну OPEN shift. Podologist отримує `403`;
permission перевіряється до object lookup, щоб endpoint не розкривав існування
payment за UUID.

Canonical payload hash обчислюється після trim/default normalization. Refund
hash включає `payment_id` із path та `reason`. Cash-movement hash включає
`type`, `amount_minor`, `reason`, `comment`.

Idempotency scopes:

- `PAYMENT` — існуючий payment family;
- `REFUND` — усі refund mutations actor;
- `CASH_MOVEMENT` — спільний family для `DEPOSIT` і `WITHDRAWAL`.

Той самий cash-movement key не може провести спочатку `DEPOSIT`, а потім
`WITHDRAWAL`. Exact key+payload повертає original operation; той самий key з
іншим normalized payload повертає `409 idempotency_payload_mismatch`. Replay
перевіряється до current state/shift guards, тому успішна повторна відповідь не
зникає після `PAID → REFUNDED` або подальшого закриття shift.

Stable domain errors:

- `409 cash_shift_required`;
- `409 payment_already_refunded`;
- `409 payment_not_refundable`;
- `409 insufficient_cash`;
- `409 idempotency_payload_mismatch`;
- `409 idempotency_key_conflict` для corrupt/reserved key без відповідного typed result;
- `422 idempotency_key_required`;
- `422 idempotency_key_invalid`;
- shared `401 authentication_required`, `403 permission_denied`,
  `404 not_found`, `422 validation_error`.

Validation, conflict або injected audit failure не створюють ledger, typed
extension, Receivable transition чи audit side effects.

## 5. Transaction і database invariants

Lock order лишається узгодженим із domain model:

- `post_refund`: Receivable → original Payment → actor CashShift;
- `post_cash_adjustment`: actor CashShift.

CashShift lock береться до availability calculation та ledger insert, тому
concurrent cash refund/withdrawal не можуть разом витратити один залишок.
Expected physical cash рахується лише з target shift ledger:

```text
CASH payments - CASH refunds + DEPOSIT - WITHDRAWAL
```

Refund transaction атомарно створює refund ledger entry, immutable Refund,
переводить Receivable `PAID → REFUNDED` і пише `billing.refund_posted` audit.
Cash adjustment атомарно створює ledger entry, immutable CashAdjustment і
`cash.deposit_posted` або `cash.withdrawal_posted` audit. Audit failure
відкочує всю transaction.

Migration/DB gates мають додати:

- `Refund` one-to-one з original Payment і refund ledger entry;
- `CashAdjustment` one-to-one з deposit/withdrawal ledger entry;
- actor name/email snapshots для обох typed extensions;
- model/queryset/admin append-only guards;
- Receivable lifecycle guard для єдиного переходу `PAID → REFUNDED`;
- ledger insert guard open-owner shift і non-negative physical cash для CASH
  refund/withdrawal;
- typed triggers, які звіряють refund amount/method/original state та
  cash-adjustment kind/no-method;
- reciprocal deferred triggers: кожен `REFUND`, `DEPOSIT`, `WITHDRAWAL` ledger
  row має рівно один правильний typed extension, а кожен Refund завершується
  Receivable у status `REFUNDED`;
- DB uniqueness для one Refund per Payment і actor+idempotency-family+key.

До встановлення reciprocal triggers migration виконує preflight існуючих
`REFUND`, `DEPOSIT`, `WITHDRAWAL` ledger rows. Попередні публічні API їх не
створювали, тому очікується нуль. Якщо legacy/raw rows існують без typed
extension, migration abort-иться з точним actionable error замість вигаданого
backfill reason або original Payment link. Reverse migration так само
відхиляється, якщо Refund/CashAdjustment rows вже існують.

## 6. UI та acceptance gates

Refund picker використовує `type=PAYMENT&status=PAID&refundable_only=true` і
підтримує пошук за patient, payment number, date та exact amount. Після вибору
UI показує original payment/visit/services, повну read-only суму, inherited
read-only method, required reason і окреме destructive confirmation. Amount
input та method select у refund form відсутні.

Deposit/withdrawal мають окремі форми лише з amount, reason і optional comment.
Patient і payment-method controls відсутні у DOM та request body. Withdrawal
показує available cash поточної shift і recoverable server conflict після
конкурентної зміни залишку.

Успіх оновлює finance operations і current-shift projection. Після ambiguous
network failure UI блокує зміну payload та повторює той самий key/body. Dialogs
мають dirty-close confirmation, focus trap/return, body scroll lock, keyboard
semantics і responsive desktop/tablet/mobile layout. Component/OpenAPI tests
окремо доводять відсутність заборонених AC-15 fields.

Mandatory gates:

- all three methods для full refund та exact method inheritance;
- double/concurrent refund — рівно один результат;
- same-shift і cross-shift refund;
- cash refund/withdrawal insufficient, equal-boundary та concurrent checks;
- exact replay, mismatch і audit-failure rollback для обох endpoints;
- negative schemas для amount/method/patient/unknown fields;
- immutable snapshots після зміни patient/user/source records;
- projection/filter/cursor tests для всіх tagged variants;
- DB raw-SQL orphan/update/delete/wrong-link/negative-cash rejection;
- component, accessibility, production build і responsive browser evidence.

## 7. Не входить до TP-703

- partial refund, custom refund amount, кілька refunds або partial-refund state;
- вибір іншого refund method, split tender та installments;
- refund cancellation/reversal, edit/delete payment/refund/cash adjustment;
- compensating cash correction workflow поза явно погодженим новим packet;
- opening-balance change, shift close/reconciliation/history — TP-704;
- receipt print/send, export, analytics, global search і notifications;
- acquiring/provider API, provider transaction ID або автоматичний рух коштів;
- multi-currency, bank settlement/reconciliation і зовнішня бухгалтерія.
