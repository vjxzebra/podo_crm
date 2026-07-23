# TP-1007 — безпечний CSV export журналу дій

Дата фіксації: 2026-07-23

Статус: `done`.

## 1. Рішення та privacy boundary

TP-1007 реалізує prototype `#exportAuditLog` як окремий admin-only export
наявного append-only журналу `GET /api/v1/audit-events`.

- admin отримує CSV;
- reception і podologist отримують `403`, anonymous — `401`;
- export є read-only і не створює domain/audit mutation;
- PostgreSQL `AuditEvent` лишається єдиним джерелом фактів.

CSV містить мінімальну list-level projection: immutable event UUID, локальний
час, historical actor name/role, section/action, object type/label, result та
generic description. Він не містить actor email/ID, object ID, `before`,
`after`, `changes`, note, correlation ID, password/security values, clinical
payload або довільні raw snapshots.

## 2. API та filter contract

`GET /api/v1/audit-events/export` приймає тільки applied filters головного
audit journal:

- `search` — trimmed, max 255;
- `actor_id` — positive integer;
- `section` — registered `AuditSection`;
- `date_from`, `date_to` — optional inclusive ISO timestamps.

Reverse range повертає `422`; якщо задані обидві межі, window не може
перевищувати 366 днів. `cursor` та будь-які інші query parameters повертають
`422 audit_export_query_not_supported`.

Endpoint використовує ті самі queryset filters і stable ordering
`occurred_at DESC, id DESC`, що й list, але без pagination. Hard limit —
`5000` event rows; selector читає `limit + 1`, а перевищення повертає
`422 audit_export_too_large` без partial CSV.

Успіх:

- `200 text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="audit-events-{timestamp}.csv"`;
- `Cache-Control: no-store`;
- `X-Export-Event-Count`;
- `X-Export-Row-Count` — summary + event rows.

## 3. CSV contract

Файл використовує RFC 4180 quoting, comma delimiter, CRLF і UTF-8 BOM.
Стабільна 28-колонкова схема:

1. `row_type`;
2. `filter_search`;
3. `filter_actor_id`;
4. `filter_section`;
5. `filter_date_from`;
6. `filter_date_to`;
7. `event_count`;
8. `accounts_count`;
9. `team_count`;
10. `settings_count`;
11. `patients_count`;
12. `work_items_count`;
13. `scheduling_count`;
14. `medical_count`;
15. `visits_count`;
16. `billing_count`;
17. `cash_count`;
18. `inventory_count`;
19. `event_id`;
20. `occurred_at_local`;
21. `actor_name`;
22. `actor_role`;
23. `section`;
24. `action`;
25. `object_type`;
26. `object_label`;
27. `result`;
28. `description`.

Перший data row завжди `REPORT_SUMMARY`, включно з empty result. Далі
`AUDIT_EVENT` rows у list order. Summary містить загальну кількість та counts
для всіх 11 registered sections.

Усі text cells проходять shared NUL/formula sanitizer. `occurred_at_local`
серіалізується як ISO 8601 у `Europe/Kyiv`; UUID та numeric cells не
локалізуються.

## 4. UI contract

CTA `Експортувати CSV` розташована в page heading `/audit` і:

- доступна тільки admin разом із самою route;
- використовує останній застосований `query`, а не draft fields;
- не передає cursor і не залежить від завантажених pages;
- disabled під час initial/reload/list error/export pending;
- показує `Готуємо CSV…`, success та error/retry;
- використовує server filename;
- не приховує filters, list, selected detail або cursor state;
- має target не менше 44px на desktop/tablet/mobile.

## 5. Не входить

- non-admin export або зміна audit route/list/detail visibility;
- `before/after/changes`, note, correlation ID, actor email/ID чи object ID;
- retention, signing, legal archive, background jobs або scheduled delivery;
- PDF/XLSX/ZIP та довільний saved-filter/report builder.

## 6. Обов’язковий доказ

- stable 28 columns, summary-first, empty report і deterministic order;
- exact five-filter parity, unsupported-query rejection, 366-day/5000-row bounds;
- admin-only `401/403`, no partial file;
- all-section totals і list/export order parity;
- absence of snapshot/note/correlation/email/object-ID/clinical/security payload;
- BOM/CRLF/quoting/formula/NUL safety і local timestamps;
- no domain/audit mutation;
- OpenAPI snapshot, generated TypeScript schema та component states;
- authenticated live HTTP і desktop/tablet/mobile browser gate.

## 7. Результат

Контракт реалізовано 2026-07-23 без розширення privacy boundary. Focused gates
пройшли `6/6` backend і `8/8` AuditPage scenarios; canonical gates —
`407/407` backend, `213/213` frontend та `40/40` axe. OpenAPI/types,
production build/image, authenticated live HTTP bytes/headers і responsive
browser QA на `1440×1000`, `768×1024`, `390×844` green.

[Повний evidence](../evidence/tp-1007/README.md).
