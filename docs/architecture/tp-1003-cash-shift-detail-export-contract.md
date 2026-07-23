# TP-1003 — безпечний CSV export однієї касової зміни

Дата фіксації: 2026-07-23

Статус: `done` 2026-07-23.

## 1. Рішення та privacy boundary

TP-1003 погоджує лише export exact cash-shift detail, уже доступного через
`GET /api/v1/cash-shifts/{shift_id}`. Новий endpoint не розширює object scope:

- admin може експортувати будь-яку видиму касову зміну;
- reception може експортувати лише власну зміну;
- foreign reception отримує non-disclosing `404`;
- podologist отримує `403`, anonymous — `401`.

CSV не приєднує typed Payment/Refund extensions і фізично не містить patient id,
ПІБ/телефон пацієнта, visit/service snapshots або клінічні дані. Employee та actor
snapshots повторюють уже видимий cash-shift detail.

## 2. API contract

`GET /api/v1/cash-shifts/{shift_id}/export` повертає exact read-only snapshot
відкритої або закритої зміни.

Успіх:

- `200 text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="cash-shift-{public_number}-{YYYYMMDD-HHMMSS}.csv"`;
- `Cache-Control: no-store`;
- `X-Export-Entry-Count` — кількість append-only ledger entries;
- `X-Export-Row-Count` — summary row плюс ledger rows.

Export має hard limit `5000` ledger entries. Якщо точна зміна перевищує ліміт,
сервер повертає `422 cash_shift_export_too_large` без partial file. Endpoint не
приймає filters/cursor, не змінює domain state і не створює audit mutation event.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF та UTF-8 BOM. Порядок
колонок стабільний:

1. `row_type` — `SHIFT_SUMMARY` або `LEDGER_ENTRY`;
2. `shift_number`;
3. `shift_status`;
4. `shift_opened_at_local`;
5. `shift_closed_at_local`;
6. `shift_employee_name`;
7. `shift_employee_email`;
8. `currency` — `UAH`;
9. `operations_count`;
10. `revenue_minor`;
11. `expected_cash_minor`;
12. `actual_cash_minor`;
13. `discrepancy_minor`;
14. `close_comment`;
15. `closed_by_name`;
16. `closed_by_email`;
17. `entry_posted_at_local`;
18. `entry_number`;
19. `entry_kind`;
20. `payment_method`;
21. `signed_amount_minor`;
22. `actor_name`;
23. `actor_email`.

Перший data row завжди `SHIFT_SUMMARY`; тому навіть зміна без операцій містить
authoritative totals/reconciliation. Далі йдуть `LEDGER_ENTRY` у порядку
`posted_at DESC, id DESC`; shift identity повторюється в кожному рядку, summary
поля у ledger rows порожні.

`signed_amount_minor` є додатним для `PAYMENT`/`DEPOSIT` та від’ємним для
`REFUND`/`WITHDRAWAL`. Server-owned numbers лишаються numeric text. Усі
user-controlled text cells отримують leading apostrophe, якщо перший non-space
символ — `=`, `+`, `-` або `@`; NUL видаляється.

## 4. UI contract

У footer exact shift detail з’являється `Експортувати CSV`. CTA:

- завжди експортує тільки `shift.id` відкритого dialog;
- показує `Готуємо CSV…`, disabled pending state і не допускає double click;
- використовує server filename та browser download;
- показує окремі success/error/retry states, не закриває dialog і не приховує
  ledger/reconciliation;
- має touch target не менше `44px` на tablet/mobile.

## 5. Не входить

- period/history або multi-shift export;
- загальний finance operations export;
- patient/payment/refund/visit/service details;
- analytics та audit export;
- receipt print/send, PDF/XLSX/ZIP, email і background jobs;
- нові models, migrations, totals або audit mutation.

## 6. Обов’язковий доказ

- exact 23-column contract, summary-first/empty shift, stable ledger order;
- sign/method mapping, Kyiv timestamps, BOM/CRLF/quoting/formula/NUL safety;
- 5000-entry bound і no partial response;
- owner/admin/foreign reception/podologist/anonymous scope;
- no patient/service joins, no domain/audit mutation;
- OpenAPI snapshot та generated TypeScript types;
- component success/loading/error/retry/server filename tests;
- authenticated live HTTP і desktop/tablet/mobile browser gate.

## 7. Результат

Контракт реалізовано без розширення scope: exact export використовує той самий
admin/owner selector, що й detail, не приєднує patient/payment/visit/service дані
та не створює mutation/audit event. Canonical gate пройшов `385/385` backend і
`204/204` frontend tests, включно з `40/40` accessibility scenarios. Live HTTP
та responsive browser evidence: [TP-1003](../evidence/tp-1003/README.md).
