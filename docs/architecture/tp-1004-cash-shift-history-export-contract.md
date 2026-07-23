# TP-1004 — безпечний CSV export історії касових змін

Дата фіксації: 2026-07-23

Статус: `done` 2026-07-23.

## 1. Рішення та privacy boundary

TP-1004 погоджує лише filtered summary report для вже доступного
`GET /api/v1/cash-shifts`. Новий endpoint не розширює role/object scope:

- admin експортує всі видимі зміни або звужує їх за працівником;
- reception експортує лише власні зміни й не може застосувати `employee_id`;
- podologist отримує `403`, anonymous — `401`.

Report використовує тільки cash-shift, employee та close snapshots і
ledger-derived агрегати. Він не містить окремих ledger rows, actor rows,
Payment/Refund extensions, patient id/name/phone, visit/service snapshots або
clinical data.

## 2. API та filter contract

`GET /api/v1/cash-shifts/export` приймає ті самі applied filters, що й history
list, крім cursor:

- `search` — trimmed, max 255; номер зміни або employee snapshot name/email;
- `date_from`, `date_to` — optional inclusive dates за `opened_at` у
  `Europe/Kyiv`; reverse range — `422`; замкнений період — не більше 366 днів;
- `status` — optional `OPEN|CLOSED`;
- `employee_id` — optional positive integer, тільки admin;
- `cursor` завжди дає `422 cash_shift_history_export_cursor_not_supported`.

Default ordering: `opened_at DESC, id DESC`. Export має hard limit `5000`
cash shifts; selector читає `limit + 1`, а перевищення повертає
`422 cash_shift_history_export_too_large` без partial CSV.

Успіх:

- `200 text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="cash-shift-history-{YYYYMMDD-HHMMSS}.csv"`;
- `Cache-Control: no-store`;
- `X-Export-Shift-Count` — кількість shift rows;
- `X-Export-Row-Count` — один report summary row плюс shift rows.

Endpoint read-only, не створює domain/audit mutation і не змінює pagination
state основного list.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF та UTF-8 BOM.
Стабільні 28 колонок:

1. `row_type` — `REPORT_SUMMARY` або `CASH_SHIFT`;
2. `shift_number`;
3. `shift_status`;
4. `opened_at_local`;
5. `closed_at_local`;
6. `employee_name`;
7. `employee_email`;
8. `currency` — `UAH`;
9. `shift_count`;
10. `open_shift_count`;
11. `closed_shift_count`;
12. `operations_count`;
13. `payment_count`;
14. `refund_count`;
15. `payments_total_minor`;
16. `refunds_total_minor`;
17. `revenue_minor`;
18. `cash_net_minor`;
19. `card_net_minor`;
20. `transfer_net_minor`;
21. `deposits_minor`;
22. `withdrawals_minor`;
23. `expected_cash_minor`;
24. `actual_cash_minor`;
25. `discrepancy_minor`;
26. `close_comment`;
27. `closed_by_name`;
28. `closed_by_email`.

Перший data row завжди `REPORT_SUMMARY`: навіть empty result має один рядок із
нульовими counts/totals. Далі йдуть `CASH_SHIFT` rows у stable order. Summary
агрегує ledger totals усіх відфільтрованих shifts; actual/discrepancy — тільки
закриті shifts. У відкритої shift close/reconciliation cells порожні.

Numeric values лишаються numeric text. Усі user-controlled snapshot/comment
cells отримують leading apostrophe, якщо перший non-space символ — `=`, `+`,
`-` або `@`; NUL видаляється.

## 4. UI contract

CTA `Експортувати CSV` розташована тільки в header історії касових змін і:

- використовує останній застосований `query`, а не незастосовані form fields;
- ніколи не передає cursor і не залежить від кількості вже завантажених pages;
- показує `Готуємо CSV…`, disabled pending, success та окремий error/retry;
- використовує server filename й не приховує filters, rows/cards або detail;
- має target не менше `44px` на desktop/tablet/mobile.

## 5. Не входить

- exact ledger export однієї shift — TP-1003;
- ledger entries у period/history file;
- finance operations, patient/visit/service, analytics або audit export;
- period KPI UI чи нові aggregate models;
- PDF/XLSX/ZIP, email, print і background jobs.

## 6. Обов’язковий доказ

- stable 28 columns, summary-first, empty report і deterministic order;
- applied filter parity, admin/own scope, employee filter denial, 401/403;
- 5000-shift/366-day bounds, cursor rejection і no partial file;
- local timestamps, BOM/CRLF/quoting/formula/NUL safety;
- aggregate reconciliation та no patient/visit/service/payment joins;
- no domain/audit mutation;
- OpenAPI snapshot, generated TypeScript schema та component states;
- authenticated live HTTP і desktop/tablet/mobile browser gate.

## 7. Результат реалізації

Contract реалізовано без розширення frozen scope. Focused gates пройшли
`5/5` нових backend scenarios, `10/10` разом із exact-shift export і `143/143`
frontend scenarios. Canonical gate: `390/390` backend, `206/206` frontend та
`40/40` accessibility. Authenticated HTTP і responsive browser QA підтвердили
CSV bytes/headers, applied-filter query, summary-first 28-column projection,
44px CTA, збереження history rows/cards, відсутність page overflow і чисту
console. [Повний evidence](../evidence/tp-1004/README.md).
