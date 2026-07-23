# TP-1006 — безпечний CSV export фінансових операцій

Статус: `done` 2026-07-23.

## Реалізований scope

- `GET /api/v1/finance/operations/export` використовує ті самі queryset
  filters, snapshot read models і stable ordering, що й головний finance
  journal, але без pagination.
- Admin-only CSV приймає рівно шість applied filters, має UTF-8 BOM,
  RFC 4180 quoting, CRLF, `no-store`, server filename,
  `X-Export-Operation-Count` і `X-Export-Row-Count`. Hard bounds — `5000`
  operations та `366` inclusive days без partial response.
- Stable 41-column report починається з `REPORT_SUMMARY`, включно з empty
  result, а далі містить deterministic `FINANCE_OPERATION` rows з
  reconciled type/status totals і `cash_effect_minor`.
- Report не містить phone, email, internal UUID, raw ledger/audit/clinical
  fields. Усі text cells проходять shared NUL/formula sanitizer.
- Admin CTA `Експортувати CSV` використовує лише останній applied query,
  блокується під час initial/reload/error/invalid/pending state, приймає server
  filename і показує success/error/retry без приховування shift summary,
  filters та operation rows. Reception зберігає журнал без export CTA.

## Автоматизовані gates

- Focused backend: `6/6` — summary/totals/order/privacy/no-audit-mutation,
  exact six-filter parity, empty report, RBAC/range/unsupported query, row
  bound/no partial та NUL-before-formula safety.
- Focused frontend: `28/28`, включно з `3` новими TP-1006 scenarios —
  applied query/disabled/pending/server filename/content preservation,
  error/retry та відсутність CTA для reception.
- Canonical: `401/401` backend, `211/211` frontend, `40/40` axe.
- Ruff і formatter перевірили `256` Python files; mypy — `193` source files.
  Django checks, migrations, OpenAPI snapshot, generated TypeScript schema,
  contracts, ESLint, strict typecheck, production build і production `web`
  image — green.

## Live HTTP

Authenticated admin probe з applied `type`, `date_from` і `date_to`
підтвердив:

- login `200`, export `200`;
- `text/csv; charset=utf-8`, `finance-operations-…csv`,
  `Cache-Control: no-store`;
- UTF-8 BOM і CRLF;
- `41` columns, first row `REPORT_SUMMARY`;
- `X-Export-Operation-Count: 1`, `X-Export-Row-Count: 2` і рівно `2`
  parsed data rows;
- query містив лише три applied filter keys.

Credentials читалися лише з Git-ignored `.env.local` і не потрапляли в
output. Endpoint не створив domain або audit mutations.

## Responsive browser QA

Authenticated in-app browser підтвердив success state, збереження shift,
filters і operation content та чисту console на трьох viewport:

- `1440×1000`: CTA `141.65×44px`, `0` horizontal overflow, success,
  operation table і shift присутні;
- `768×1024`: CTA `587.20×44px`, `0` horizontal overflow, success,
  filters, operation card і shift присутні;
- `390×844`: CTA `347.20×44px`, `0` horizontal overflow, success,
  filters, operation content і shift присутні в DOM.

Артефакти:

- [desktop success](desktop-finance-export-success.png)
- [tablet success](tablet-finance-export-success.png)
- [mobile success](mobile-finance-export-success.png)

## Runtime recovery

Паралельний запуск lint, typecheck і Vitest перевантажив три одночасні Node
containers, через що Vitest завершився `SIGSEGV`. Стан Compose/resources і
відсутність залишкового test container перевірено; після виправлення двох lint
зауважень sequential Vitest стабільно запустився, виявив реальну relative-URL
помилку, а після її виправлення focused suite пройшов `28/28`.

Перший canonical wrapper був перерваний зовнішнім timeout, тоді як дочірній
backend-test лишився без stdout consumer і завис на `53%`. Container не
реагував на точкові stop/SIGKILL, що підтвердило zombie-стан Docker daemon.
Штатний restart Docker Desktop прибрав лише завислий container/test DB;
`docker compose up -d --wait` відновив healthy stack і readiness `200` без
видалення volumes. Повторний canonical gate завершився повністю за `99s`.

Перший memory-only HTTP parser помилково очікував scalar замість PowerShell
`String[]` для заголовка. Endpoint уже відповідав; parser звужено до першого
значення, після чого probe пройшов без запису CSV на диск. Browser viewport
скинуто через authoritative `reset()`, вкладку закрито.

Фінальний hygiene probe спочатку звернувся до незадіяного host port `80` і
отримав `connection refused`. Compose inspection підтвердив configured proxy
mapping `8088:80`; правильний `/health/ready` повернув `200`, а
proxy/backend/web лишалися healthy, тому restart або mutation не виконувалися.
