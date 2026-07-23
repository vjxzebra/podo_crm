# TP-1003 — безпечний CSV export однієї касової зміни

Статус: `done` 2026-07-23.

## Реалізований зріз

- `GET /api/v1/cash-shifts/{shift_id}/export` повторює exact detail scope:
  admin бачить видиму зміну, reception — лише власну, foreign reception отримує
  non-disclosing `404`, podologist — `403`, anonymous — `401`.
- Summary-first CSV має стабільні 23 колонки, RFC 4180 quoting, CRLF, UTF-8 BOM,
  `Europe/Kyiv` timestamps і signed minor-unit ledger amounts. Порожня зміна все
  одно містить authoritative `SHIFT_SUMMARY`.
- Export обмежено 5000 ledger entries з `422` без partial file; endpoint не
  приймає query params, не змінює domain/audit state і не приєднує typed
  Payment/Refund, patient, visit, service, phone або clinical data.
- Response повертає `Cache-Control: no-store`, entry/row counts і server-owned
  attachment filename. Shared sanitizer видаляє NUL і захищає user-controlled
  text від spreadsheet-formula injection без перетворення numeric cells.
- Exact detail dialog отримав pending/disabled, success, error/retry й server
  filename download, зберігаючи ledger/reconciliation та сам dialog видимими.

## Automated gates

- focused cash-shift export backend: `5/5`; focused shared inventory/cash CSV:
  `13/13`;
- focused frontend: `141/141`, у тому числі `7/7` cash-shift history scenarios
  та `40/40` accessibility scenarios;
- canonical backend: `385/385`; canonical frontend: `204/204` у 13 files,
  включно з `40/40` accessibility scenarios;
- Ruff/format для 253 Python files, mypy для 192 source files, Django checks,
  clean migration cycle, OpenAPI snapshot, generated TypeScript schema,
  contracts, ESLint, strict typecheck і production build — green.

## Runtime та browser evidence

Authenticated read-only HTTP probe на existing open shift підтвердив `200`,
`text/csv; charset=utf-8`, UTF-8 BOM, `Cache-Control: no-store`, server filename,
`X-Export-Entry-Count: 1` і `X-Export-Row-Count: 2` для exact URL без query.
Runtime download event/file handle у in-app browser не підтримується, тому file
bytes/headers доведено live HTTP та backend integration tests.

In-app browser підтвердив exact-detail CTA, success-state та незмінний ledger на
`1440×1000`, `768×1024` і `390×844`. Horizontal document overflow відсутній;
dialog лишається в межах viewport, export target має `44px`, на mobile займає
`345.6px` із `390px`, console містить `0` записів. Тимчасовий viewport override
скинуто, QA-вкладку закрито.

Після runtime recreate перший readiness probe потрапив у коротке startup-вікно
та повернув `502`. Окрема recovery-перевірка журналів підтвердила connection
refused до моменту запуску Django; backend/web/proxy перейшли в healthy без
додаткової мутації, мінімальний повторний probe повернув `200`. Volumes і domain
records не видалялися. Локальні credentials читалися лише з Git-ignored
`.env.local` і не записувалися до tracked output.

- [Desktop success state](desktop-export-success.png)
- [Tablet success state](tablet-export-success.png)
- [Mobile success state](mobile-export-success.png)
