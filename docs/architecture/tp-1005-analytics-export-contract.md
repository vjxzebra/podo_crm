# TP-1005 — безпечний CSV export агрегованої аналітики

Дата фіксації: 2026-07-23

Статус: `done` 2026-07-23.

## 1. Рішення та privacy boundary

TP-1005 реалізує лише aggregate report для вже доступного admin-only
`GET /api/v1/analytics`. Новий endpoint не розширює role scope:

- admin із analytics scope отримує report;
- reception і podologist отримують `403`;
- anonymous отримує `401`.

CSV містить лише ті KPI та aggregate dimensions, які вже повертає analytics
read model: trend buckets, appointment outcomes, specialist performance і
service ranking. Він не містить patient id/name/phone, visit/appointment/payment/
refund identifiers, ledger rows, complaints, photos або інших clinical data.

## 2. API та filter contract

`GET /api/v1/analytics/export` приймає той самий applied query, що й analytics:

- `from`, `to` — обов’язкові inclusive dates у `Europe/Kyiv`;
- reverse range — `422`;
- замкнений період — не більше 366 днів;
- `specialist_id` — optional positive integer;
- `service_id` — optional UUID;
- невідомий specialist/service повторює existing non-disclosing `404`.

Endpoint викликає один canonical `analytics_read_model`, тому KPI, filters,
ordering і snapshot semantics збігаються з видимою сторінкою. Report має hard
limit `5000` data rows; перевищення повертає
`422 analytics_export_too_large` без partial CSV.

Успіх:

- `200 text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="analytics-report-{YYYYMMDD-HHMMSS}.csv"`;
- `Cache-Control: no-store`;
- `X-Export-Row-Count` — кількість data rows без header.

Endpoint read-only, не створює domain/audit mutation.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF та UTF-8 BOM.
Стабільні 34 колонки:

1. `row_type`;
2. `period_from`;
3. `period_to`;
4. `timezone`;
5. `bucket`;
6. `filter_specialist_id`;
7. `filter_specialist_name`;
8. `filter_service_id`;
9. `filter_service_name`;
10. `sequence`;
11. `dimension_from`;
12. `dimension_to`;
13. `dimension_id`;
14. `dimension_code`;
15. `dimension_name`;
16. `is_active`;
17. `completed_visits`;
18. `revenue_minor`;
19. `payment_count`;
20. `average_check_minor`;
21. `returning_patient_rate_bps`;
22. `returning_patients`;
23. `served_patients`;
24. `new_patients`;
25. `canceled_appointments`;
26. `no_show_appointments`;
27. `average_return_interval_days`;
28. `visits`;
29. `appointment_count`;
30. `scheduled_minutes`;
31. `available_minutes`;
32. `utilization_bps`;
33. `quantity`;
34. `billed_total_minor`.

Перший data row завжди `REPORT_SUMMARY` з усіма KPI та applied filter
snapshots. Далі у deterministic order:

1. `TREND` — chronological buckets із visits/revenue;
2. `APPOINTMENT_OUTCOME` — canonical `COMPLETED`, `CANCELED`, `NO_SHOW`,
   `OTHER`;
3. `SPECIALIST_PERFORMANCE` — existing utilization sort;
4. `SERVICE_RANKING` — existing quantity/revenue/name sort.

Empty analytics все одно має `REPORT_SUMMARY`, canonical outcome rows і trend
buckets із нульовими значеннями. Nullable average return interval лишається
порожньою numeric cell. Numeric values не перетворюються на localized text.
Усі directory/snapshot text cells проходять shared NUL/formula sanitizer.

## 4. UI contract

CTA `Експортувати CSV` розташована у heading `/analytics` поруч із
`Ledger-звірено` і:

- активна лише після успішного завантаження current projection;
- використовує server-returned `analytics.period` та `analytics.filters`, а не
  query, що ще завантажується або завершився помилкою;
- показує `Готуємо CSV…`, disabled pending, success та error/retry;
- використовує server filename й не приховує KPI, charts або tables;
- має target не менше `44px` на desktop/tablet/mobile.

## 5. Не входить

- patient/visit/appointment/payment/refund або ledger rows;
- finance-operation чи audit journal export;
- зміна analytics формул, filters, ordering або page content;
- PDF/XLSX/ZIP, email, print і background jobs.

## 6. Обов’язковий доказ

- stable 34 columns, summary-first, deterministic section order та empty report;
- exact filter/read-model parity, admin-only `401/403`, invalid range/entity;
- 5000-row bound і no partial file;
- BOM/CRLF/quoting/formula/NUL safety;
- aggregate reconciliation без raw patient/clinical/operation identifiers;
- no domain/audit mutation;
- OpenAPI snapshot, generated TypeScript schema та component states;
- authenticated live HTTP і desktop/tablet/mobile browser gate.

## 7. Результат

Контракт реалізований без розширення analytics privacy/RBAC boundary. Focused
gates: `8/8` analytics backend і `140/140` frontend/accessibility. Canonical
gates: `395/395` backend, `208/208` frontend і `40/40` axe; OpenAPI/types та
production build green. Authenticated HTTP підтвердив BOM, CRLF, 34 columns,
summary-first, exact four applied filters і header/parser parity `37/37`.
Responsive browser gate на `1440×1000`, `768×1024` і `390×844` підтвердив
success state, 44px CTA, збереження KPI/tables, відсутність horizontal overflow
та clean console. [Evidence](../evidence/tp-1005/README.md).
