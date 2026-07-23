# TP-702: контракт повної оплати

- Стан реалізації: `done` 2026-07-22
- Джерела: SPEC §9.1–9.3, AC-13—AC-14, ADR-006, `docs/architecture/domain-model.md`
- Межа пакета: повна оплата завершеного прийому та paid/unpaid finance projection

Цей документ фіксує реалізований і перевірений контракт TP-702. Після закриття
implementation gates він лишається замороженою межею для TP-703/TP-704.

## 1. Список фінансових операцій

`GET /api/v1/finance/operations` повертає paid+unpaid union із рівно одним
стабільним рядком на `Receivable`. Проведення оплати змінює projection цього
рядка з `OPEN` на `PAID`, а не додає другий рядок поруч із неоплаченим.

Query parameters:

| Поле | Тип і правило |
|---|---|
| `search` | optional string, max 255; ім'я/прізвище, телефон, номер пацієнта, visit/payment number, snapshot code/name послуги |
| `type` | optional enum; у TP-702 єдине значення `PAYMENT` |
| `status` | optional enum `OPEN\|PAID\|REFUNDED` |
| `date_from`, `date_to` | optional ISO date, inclusive у `Europe/Kyiv`; зворотний діапазон — `422` |
| `payment_method` | optional enum `CASH\|CARD\|TRANSFER`; unpaid rows не збігаються |
| `patient_id` | optional UUID для звуження вибраного пацієнта до його прийомів |
| `cursor` | optional opaque string |

Default ordering: `occurred_at DESC, id DESC`; page size — 40. Для `OPEN`
`occurred_at` дорівнює `visit.completed_at`, для проведеної оплати —
`payment.posted_at`.

Response:

```json
{
  "operations": [
    {
      "id": "receivable-uuid",
      "type": "PAYMENT",
      "status": "OPEN",
      "occurred_at": "2026-07-22T10:00:00Z",
      "amount_minor": 145000,
      "patient": {
        "id": "patient-uuid",
        "public_number": "PAT-...",
        "display_name": "Ім'я Прізвище",
        "phone": "+380..."
      },
      "visit": {
        "id": "visit-uuid",
        "public_number": "V-...",
        "completed_at": "2026-07-22T10:00:00Z",
        "payment_handoff_requested": true,
        "total_minor": 145000,
        "specialist": {"id": 7, "name": "Ім'я Прізвище"},
        "services": [
          {
            "id": "line-uuid",
            "code": "SERVICE-CODE",
            "name": "Назва",
            "quantity": 1,
            "unit_price_minor": 145000,
            "line_total_minor": 145000
          }
        ]
      },
      "payment": null
    }
  ],
  "next_cursor": null
}
```

`payment` — єдине nullable поле operation projection. Для проведеної оплати
воно містить `id`, `ledger_entry_id`, `public_number`, `payment_method`,
non-null `comment` (може бути порожнім), `posted_at`, actor
`{id, name}` і cash shift `{id, public_number}`. Виняток —
автоматично врегульований нульовий receivable: `status=PAID`,
`payment=null`.

Список містить усі completed receivables незалежно від
`payment_handoff_requested`: цей прапорець є workflow hint, а не дозволом
приховати заборгованість. Projection містить лише safe finance/contact/service
snapshots і не серіалізує скарги, огляд, медичні нотатки, фото чи рекомендації.

## 2. Проведення повної оплати

`POST /api/v1/payments` потребує header `Idempotency-Key`: trimmed non-empty
string, max 128.

Request із `additionalProperties: false`:

```json
{
  "visit_id": "visit-uuid",
  "payment_method": "CASH",
  "comment": "Необов'язковий коментар"
}
```

- `visit_id` і `payment_method` required;
- `comment` optional, trim, max 2000, default `""`;
- `amount_minor`, `receivable_id`, `cash_shift_id`, actor і status не
  приймаються;
- amount завжди копіюється сервером із immutable `Receivable.amount_minor`;
- один payment має рівно один method і повністю закриває один receivable.

Нова mutation повертає `201`, replay того самого key+payload — `200`:

```json
{
  "operation": {"id": "receivable-uuid", "type": "PAYMENT"},
  "replayed": false
}
```

`operation` використовує повний read model із розділу 1.

## 3. Транзакція, scope та помилки

Admin і reception читають clinic-wide safe finance projection, але нову оплату
проводять лише у власну `OPEN` cash shift. Podologist отримує `403`.

Payment service в одній транзакції lock-ить receivable, потім власну cash
shift, повторно перевіряє `OPEN` state, створює append-only ledger entry і
immutable Payment, переводить receivable `OPEN → PAID` та пише
`billing.payment_posted` audit із before/after і correlation ID. Audit failure
відкочує всі записи. Unique `Payment.receivable_id` і
`Payment.ledger_entry_id` разом із ledger idempotency constraint гарантують
один результат при concurrent submit.

Stable domain errors:

- `409 cash_shift_required`;
- `409 receivable_already_paid`;
- `409 receivable_already_refunded`;
- `409 visit_not_payable`;
- `409 idempotency_payload_mismatch`;
- `422 idempotency_key_required`;
- `422 idempotency_key_invalid`;
- shared `401 authentication_required`, `403 permission_denied`,
  `404 not_found`, `422 validation_error`.

## 4. Нульова сума

Ledger invariant `CashLedgerEntry.amount_minor > 0` не послаблюється.
Receivable з `amount_minor=0` автоматично переходить у `PAID` під час
finish без Payment, ledger entry, open-shift requirement або
`billing.payment_posted` audit. Він не потрапляє до unpaid picker; існуючі
`OPEN` zero rows підлягають data migration до `PAID`.

## 5. Не входить до TP-702

- partial payment, custom amount, split tender та installments;
- refund, cash deposit і withdrawal mutations — TP-703;
- shift close, reconciliation та shift history — TP-704;
- export, друк/надсилання чека, acquiring/provider integration;
- редагування або видалення проведеної оплати;
- global search, notifications та analytics.

## 6. Результат implementation gates

- focused suites: 50 billing tests і 14 `FinancePage` tests;
- canonical suites: 266 backend tests, 137 frontend tests і 32 axe scenarios;
- OpenAPI snapshot, generated client/contracts, static checks і production build
  пройшли;
- dev migration smoke пройшов rollback→reapply; активні всі шість billing
  triggers, зокрема два взаємні deferred aggregate guards;
- runtime `/`, `/finance` і `/health/ready` повернув `200`;
- desktop/tablet/mobile browser gate перевірив unpaid detail і full-payment
  dialog: amount inputs `0`, payment methods `3`, body scroll lock, focus return,
  horizontal overflow `0`, console warnings/errors `0`.

Browser gate був read-only і не відправляв payment mutation. Paid та zero-settled
стани підтверджені API/component tests, а не browser fixture. Screenshots і точна
межа evidence описані в [`docs/evidence/tp-702/`](../evidence/tp-702/README.md).
