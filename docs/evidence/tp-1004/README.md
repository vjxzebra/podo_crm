# TP-1004 — безпечний CSV export історії касових змін

Статус: `done` 2026-07-23.

## Реалізований зріз

- `GET /api/v1/cash-shifts/export` повторює history-list filters без cursor:
  `search`, inclusive `date_from`/`date_to`, `status` та admin-only
  `employee_id`. Admin бачить усі доступні зміни, reception — лише власні;
  podologist отримує `403`, anonymous — `401`.
- Summary-first CSV має стабільні 28 колонок, RFC 4180 quoting, CRLF, UTF-8
  BOM, `Europe/Kyiv` timestamps і minor-unit aggregates. Навіть empty result
  містить authoritative `REPORT_SUMMARY` з нульовими підсумками.
- Export обмежено 5000 змінами та замкненим періодом у 366 днів; selector читає
  `limit + 1`, а перевищення, reverse range або cursor дають `422` без partial
  file. Порядок стабільний: `opened_at DESC, id DESC`.
- Report агрегує лише `CashShift` і `CashLedgerEntry`; individual ledger rows,
  patient/visit/service та typed Payment/Refund data не експортуються. Endpoint
  read-only і не створює domain/audit mutation.
- Response повертає `Cache-Control: no-store`, shift/row counts і server-owned
  attachment filename. Shared sanitizer видаляє NUL та захищає user-controlled
  cells від spreadsheet-formula injection, не змінюючи numeric cells.
- Header історії отримав applied-filters-only export без cursor, pending/disabled,
  success і error/retry стани. Filters, таблиця desktop/tablet, mobile cards і
  detail flow після export залишаються доступними.

## Automated gates

- новий focused backend export gate: `5/5`; разом із exact shift export:
  `10/10`;
- focused frontend: `143/143`, зокрема `9/9` cash-shift history scenarios і
  `40/40` accessibility scenarios;
- canonical backend: `390/390`; canonical frontend: `206/206` у 13 files,
  включно з `40/40` accessibility scenarios;
- Ruff/format для 254 Python files, mypy для 192 source files, Django checks,
  clean migrations, OpenAPI snapshot, generated TypeScript schema, contracts,
  ESLint, strict typecheck і production build — green.

## Runtime та browser evidence

Authenticated read-only HTTP probe з applied `search` і `status` підтвердив
`200`, `text/csv; charset=utf-8`, UTF-8 BOM, CRLF, рівно 28 колонок,
`REPORT_SUMMARY` першим data row, `Cache-Control: no-store`, server filename,
`X-Export-Shift-Count: 1`, `X-Export-Row-Count: 2` і відсутність cursor у query.
Runtime download event/file handle у in-app browser не підтримується, тому file
bytes/headers окремо доведені live HTTP та backend integration tests.

In-app browser підтвердив header CTA, success-state й незмінну history projection
на `1440×1000`, `768×1024` і `390×844`. Document horizontal overflow відсутній;
export target має `44px`, mobile CTA — `243.28px` із `375.20px` panel width,
mobile cards і desktop/tablet table лишилися видимими. Console warnings/errors:
`0`. Тимчасовий viewport override скинуто, QA-вкладки закрито.

Ручний mypy виклик спочатку впав через відсутній у runtime Python модуль
`sqlite3`: команда пропустила canonical `--no-sqlite-cache`, тоді як наявний
cache містив `cache.db`. Окрема recovery-перевірка traceback і
`backend/scripts/check.sh` підтвердила правильний режим; exact cache file
тимчасово переміщено й відновлено, мінімальний mypy з canonical flag та повний
gate пройшли. Код і cache state не потребували виправлення.

Під час browser setup capability pointer спочатку вказав на відсутній fallback
path. Пошук у точному plugin package знайшов authoritative
`docs/capabilities/browser/viewport.md`; інструкцію прочитано, viewport set/reset
перевірено мінімальним викликом, runtime browser працював штатно.

Backend/web recreated через `docker compose ... --wait`; readiness повернув
`200`. Volumes і domain records не видалялися. Локальні credentials читалися
лише з Git-ignored `.env.local` і не записувалися до tracked output.

- [Desktop success state](desktop-history-export-success.png)
- [Tablet success state](tablet-history-export-success.png)
- [Mobile full-page success state](mobile-history-export-success.png)
