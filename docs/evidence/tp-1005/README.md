# TP-1005 — безпечний CSV export агрегованої аналітики

Статус: `done` 2026-07-23.

## Реалізований scope

- `GET /api/v1/analytics/export` використовує той самий валідатор фільтрів і
  canonical analytics read model, що й екран `/analytics`.
- Admin-only CSV має UTF-8 BOM, RFC 4180 quoting, CRLF, `no-store`, server
  filename та `X-Export-Row-Count`; hard bounds — `5000` data rows і `366`
  inclusive days без partial response.
- Stable 34-column report починається з `REPORT_SUMMARY`, далі містить
  deterministic `TREND`, `APPOINTMENT_OUTCOME`, `SPECIALIST_PERFORMANCE` і
  `SERVICE_RANKING` sections.
- Report не містить raw patient/clinical data, patient/visit/appointment/
  payment/refund/ledger identifiers або finance/audit rows. Directory text
  проходить shared NUL/formula sanitizer.
- CTA `Експортувати CSV` використовує тільки current loaded projection,
  блокується під час reload/pending/error/invalid state, приймає server filename
  і показує pending/success/error/retry без приховування KPI, charts чи tables.

## Автоматизовані gates

- Analytics backend file: `8/8`, з них `5` нових TP-1005 tests — filtered
  reconciliation/order/privacy/no-audit-mutation, empty report, RBAC/range/
  missing entities, row bound/no partial та NUL-before-formula safety.
- Focused frontend: `140/140` (`6` analytics, `94` App integration, `40` axe),
  включно з current-loaded-filter, disabled reload, pending/download filename,
  error/retry та content-preservation states.
- Canonical: `395/395` backend, `208/208` frontend, `40/40` axe.
- Ruff і formatter перевірили `255` Python files; mypy — `193` source files.
  Django checks, migrations, OpenAPI snapshot, generated TypeScript schema,
  contracts, ESLint, strict typecheck і production build — green.

## Live HTTP

Authenticated admin probe з `from`, `to`, `specialist_id` і `service_id`
підтвердив:

- login `200`, export `200`;
- `text/csv; charset=utf-8`, `analytics-report-…csv`, `Cache-Control: no-store`;
- UTF-8 BOM і CRLF;
- `34` columns, first row `REPORT_SUMMARY`;
- `X-Export-Row-Count: 37` і рівно `37` parsed data rows;
- query містив лише чотири applied filter keys.

Credentials читалися лише з Git-ignored `.env.local` і не потрапляли в output.
Endpoint не створив domain або audit mutations.

## Responsive browser QA

Authenticated in-app browser підтвердив success state, збереження report
content і чисту console на трьох viewport:

- `1440×1000`: CTA `141.65×44px`, `0` horizontal overflow, KPI і дві tables
  присутні;
- `768×1024`: CTA `115.78×44px`, `0` horizontal overflow, KPI і дві tables
  присутні;
- `390×844`: CTA `351.20×44px`, `0` horizontal overflow, success, KPI і дві
  tables присутні в DOM.

Артефакти:

- [desktop success](desktop-analytics-export-success.png)
- [tablet success](tablet-analytics-export-success.png)
- [mobile success](mobile-analytics-export-success.png)

## Runtime recovery

Після recreate backend/web reverse proxy зберіг stale upstream
`172.19.0.6:8000`, тоді як healthy backend отримав `172.19.0.2`. Окрема
recovery-підзадача звірила Compose state, backend logs/IP і proxy logs, після
чого перезапустила лише `proxy`; readiness та session знову повернули `200`.
Volumes і domain data не змінювалися.

Завершальне скидання browser viewport спочатку викликало неіснуючий
`setViewportSize()`. Capability inspection показав authoritative `set/reset`
API; `reset()` і закриття вкладки пройшли успішно.
