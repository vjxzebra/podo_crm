# TP-1006 — безпечний CSV export фінансових операцій

Дата фіксації: 2026-07-23

Статус: `done`.

## 1. Рішення та privacy boundary

TP-1006 реалізує prototype admin control `data-finance-admin` як окремий
admin-only export уже наявного журналу `GET /api/v1/finance/operations`.

- admin отримує CSV;
- reception зберігає доступ до інтерактивного журналу, але export отримує
  `403`;
- podologist отримує `403`, anonymous — `401`.

CSV містить лише фінансові snapshot-поля, потрібні для звірки: публічні номери,
ім’я пацієнта, публічний номер прийому, specialist/service snapshots, спосіб,
працівника, зміну, reason/comment і суми. Телефон, email пацієнта, внутрішні UUID,
clinical fields, photos, audit payload та окремі raw ledger identifiers не
експортуються.

## 2. API та filter contract

`GET /api/v1/finance/operations/export` приймає тільки applied filters головного
finance journal:

- `search` — trimmed, max 255;
- `type` — `PAYMENT|REFUND|DEPOSIT|WITHDRAWAL`;
- `status` — `OPEN|PAID|REFUNDED|POSTED`;
- `payment_method` — `CASH|CARD|TRANSFER`;
- `date_from`, `date_to` — optional inclusive local dates.

Reverse range повертає `422`; якщо задані обидві межі, inclusive range не може
перевищувати 366 днів. `cursor`, `patient_id`, `amount_minor`,
`refundable_only` та будь-які інші query parameters повертають
`422 finance_operation_export_query_not_supported`.

Endpoint використовує ті самі queryset filters, snapshot read models і stable
ordering `occurred_at DESC, id DESC, type DESC`, що й list, але без pagination.
Hard limit — `5000` operation rows; selector читає `limit + 1`, а перевищення
повертає `422 finance_operation_export_too_large` без partial CSV.

Успіх:

- `200 text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="finance-operations-{timestamp}.csv"`;
- `Cache-Control: no-store`;
- `X-Export-Operation-Count`;
- `X-Export-Row-Count` — summary + operation rows.

Endpoint read-only і не створює domain/audit mutation.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF і UTF-8 BOM.
Стабільна 41-колонкова схема:

1. `row_type`;
2. `filter_search`;
3. `filter_type`;
4. `filter_status`;
5. `filter_payment_method`;
6. `filter_date_from`;
7. `filter_date_to`;
8. `operation_count`;
9. `payment_count`;
10. `refund_count`;
11. `deposit_count`;
12. `withdrawal_count`;
13. `open_count`;
14. `paid_count`;
15. `refunded_count`;
16. `posted_count`;
17. `outstanding_minor`;
18. `payments_minor`;
19. `refunds_minor`;
20. `deposits_minor`;
21. `withdrawals_minor`;
22. `net_posted_minor`;
23. `occurred_at_local`;
24. `operation_number`;
25. `operation_type`;
26. `operation_status`;
27. `amount_minor`;
28. `cash_effect_minor`;
29. `currency`;
30. `payment_method`;
31. `patient_number`;
32. `patient_name`;
33. `visit_number`;
34. `visit_completed_at_local`;
35. `specialist_name`;
36. `services`;
37. `cash_shift_number`;
38. `actor_name`;
39. `reason`;
40. `comment`;
41. `original_payment_number`.

Перший data row завжди `REPORT_SUMMARY`, включно з empty result. Далі
`FINANCE_OPERATION` rows у list order.

`amount_minor` завжди невід’ємна server amount. `cash_effect_minor` дорівнює:

- `0` для OPEN receivable та zero settlement;
- `+amount` для проведеної PAYMENT або DEPOSIT;
- `-amount` для REFUND або WITHDRAWAL.

Summary рахує status/type counts, outstanding, posted type totals і
`net_posted_minor` як суму `cash_effect_minor` відфільтрованих rows.

`services` — deterministic `code name ×quantity` snapshot, з’єднаний `; `.
Усі text cells проходять shared NUL/formula sanitizer; numeric cells не
локалізуються.

## 4. UI contract

CTA `Експортувати CSV` розташована у header «Фінансові операції» тільки для
admin і:

- використовує останній застосований `query`, а не draft fields;
- не передає cursor і не залежить від завантажених pages;
- disabled під час initial/reload/error/invalid/export pending;
- показує `Готуємо CSV…`, success та error/retry;
- використовує server filename;
- не приховує shift summary, filters, operation rows або dialogs;
- має target не менше 44px на desktop/tablet/mobile.

## 5. Не входить

- reception export або зміна finance list visibility;
- phone/email/internal UUID/raw ledger/audit/clinical export;
- cash-shift detail/history CSV — TP-1003/TP-1004;
- analytics CSV — TP-1005;
- audit journal export;
- PDF/XLSX/ZIP, receipt print/send і background jobs.

## 6. Обов’язковий доказ

- stable 41 columns, summary-first, empty report і deterministic order;
- exact six-filter parity, unsupported-query rejection, 366-day/5000-row bounds;
- admin-only `401/403`, no partial file;
- status/type totals та cash-effect reconciliation;
- absence of phone, UUID, raw ledger/audit/clinical fields;
- BOM/CRLF/quoting/formula/NUL safety і local timestamps;
- no domain/audit mutation;
- OpenAPI snapshot, generated TypeScript schema та component states;
- authenticated live HTTP і desktop/tablet/mobile browser gate.

## 7. Результат

Контракт реалізовано без розширення privacy/RBAC boundary. Focused gates
пройшли `6/6` backend і `28/28` frontend; canonical gate — `401/401` backend,
`211/211` frontend та `40/40` axe. Authenticated live HTTP підтвердив headers,
bytes, 41 columns, summary-first і operation/row count parity. Responsive
browser gate на `1440×1000`, `768×1024` і `390×844` підтвердив 44px CTA,
success/content-preservation states, відсутність page overflow і чисту console.

[Повний evidence](../evidence/tp-1006/README.md).
