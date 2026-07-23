# TP-1002 — безпечний CSV export журналу рухів

Дата фіксації: 2026-07-23

Статус: `done` 2026-07-23; [evidence](../evidence/tp-1002/README.md).

## 1. Рішення щодо GAP-18

TP-1002 погоджує лише один production export: admin-only CSV журналу рухів
складу. Це найменш чутливий і вже стабільний append-only read model.

Prototype controls для cash-shift history/detail, analytics та audit не входять у
TP-1002 і не з’являються у production UI. Кожен із них потребує окремого packet
із власними privacy, RBAC, retention і format рішеннями.

## 2. API contract

`GET /api/v1/inventory/movements/export` приймає ті самі applied filters, що й
журнал, крім cursor:

- `search`;
- `kind`;
- `material_id`;
- `actor`;
- `date_from`, `date_to`.

Admin отримує `200 text/csv; charset=utf-8` і attachment filename
`inventory-movements-YYYYMMDD-HHMMSS.csv`. Anonymous отримує `401`, reception і
podologist — `403`.

Export містить усі рядки, що відповідають filters, у стабільному порядку
`posted_at DESC, movement id DESC`, але не більше `5000`. Якщо результат більший,
сервер повертає `422 export_too_large` без partial file. Inclusive date range,
якщо вказані обидві межі, не може перевищувати `366` днів.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF і UTF-8 BOM для
сумісності з локальним spreadsheet software. Порядок колонок стабільний:

1. `posted_at_local` — ISO 8601 у `Europe/Kyiv`;
2. `operation_number`;
3. `operation_kind`;
4. `material_sku`;
5. `material_name`;
6. `lot_number`;
7. `supplier_id`;
8. `supplier_name` — immutable lot snapshot;
9. `quantity_delta`;
10. `unit`;
11. `balance_after`;
12. `actor_name`;
13. `actor_email`;
14. `reason`;
15. `comment`.

User-controlled text, перший non-space символ якого дорівнює `=`, `+`, `-` або
`@`, отримує leading apostrophe. NUL видаляється. Server-owned numeric columns не
перетворюються на text, тому від’ємна кількість лишається валідним числом.

Response має `Cache-Control: no-store` та `X-Export-Row-Count`. Export є
read-only GET: він не змінює domain data й не створює audit mutation event.

## 4. UI contract

У заголовку «Рухи матеріалів» з’являється `Експортувати CSV`. Кнопка:

- передає лише останні застосовані filters, а не ще не підтверджені form values;
- показує `Готуємо CSV…` і блокує повторний click;
- використовує server filename та browser download;
- показує окремий error/retry state, не руйнуючи journal rows або filters;
- має щонайменше 44px touch target на tablet/mobile.

## 5. Не входить

- XLSX, PDF, ZIP, email або background export jobs;
- configurable columns/locale/delimiter;
- cash-shift, finance-operation, analytics, audit, patient або visit export;
- scheduled reports і зовнішня передача файлу.

## 6. Доказ

- filter parity, stable headers/order, BOM/quoting/local time і empty export;
- RBAC, `5000` row bound, `366` day bound та no partial response;
- spreadsheet-formula injection regression;
- OpenAPI snapshot/generated types;
- component download/loading/error/filter tests;
- authenticated desktop/tablet/mobile browser download gate.

Результат: `8/8` focused export backend, `380/380` canonical backend,
`202/202` frontend і `40/40` accessibility scenarios. In-app browser не надає
download file handle, тому browser підтвердив CTA та success-state, а фактичні
CSV bytes/headers — authenticated live HTTP probe й integration tests.
