# TP-1002 — безпечний CSV export журналу рухів

Статус: `done` 2026-07-23.

## Реалізований зріз

- Admin-only `GET /api/v1/inventory/movements/export` повторює applied filters
  журналу без cursor і повертає не більше 5000 рядків за період до 366 днів.
- CSV має стабільні 15 колонок, RFC 4180 quoting, CRLF, UTF-8 BOM, локальний
  `Europe/Kyiv` timestamp, immutable supplier snapshot і захист user-controlled
  text від spreadsheet-formula injection та NUL.
- Response повертає `Cache-Control: no-store`, `X-Export-Row-Count` і server
  attachment filename. Перевищення ліміту дає `422` без partial file; export не
  змінює domain data й не створює audit mutation.
- Журнал отримав `Експортувати CSV` з останніми застосованими filters,
  loading/disabled, success, окремим error/retry та збереженням rows/filters.

## Automated gates

- focused inventory export backend: `8/8`;
- canonical backend: `380/380`;
- canonical frontend: `202/202` у 13 files, з них `40/40` accessibility scenarios;
- Ruff/format для 250 Python files, mypy для 190 source files, Django checks,
  migrations, OpenAPI snapshot, generated TypeScript schema, contracts, ESLint,
  strict typecheck і production build — green.

## Runtime та browser evidence

Live authenticated HTTP probe з `Accept: text/csv` підтвердив `200`,
`text/csv; charset=utf-8`, attachment filename, `X-Export-Row-Count: 3` і UTF-8
BOM. Під час gate знайдено й виправлено DRF `406` для цього Accept header;
regression-тест тепер перевіряє negotiated CSV response.

In-app browser підтвердив єдину CTA, server success-state та незмінні journal
rows. Runtime не надає download event/file handle, тому фактичні bytes і headers
перевірено live HTTP probe та backend integration tests. На `1440×1000`,
`768×1024` і `390×844` horizontal overflow відсутній; export target має `44px`,
mobile width — `164px`; console містить `0` записів. Viewport скинуто, вкладку
закрито.

Під час виконання точково відновлено writable pytest cache, перерваний 60-second
test runner і backend після renderer fix. Фінальний ephemeral backend-test
потрапив у Docker Desktop exit-event deadlock; керований Desktop restart без
видалення volumes відновив stack і свіжий runner. Наступний backend gate пройшов
`380/380`, а одноразовий V8 `Illegal instruction` у frontend відновлено minimal
Node probe та повним повтором `202/202`. Web/backend/proxy healthy,
`/health/ready` повертає `200`; domain records не видалялися.

- [Desktop success state](movement-export-desktop.png)
- [Tablet layout](movement-export-tablet.png)
- [Mobile layout](movement-export-mobile.png)
