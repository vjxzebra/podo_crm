# TP-801 — role-scoped global search

Статус: `done` 2026-07-22.

## Реалізований зріз

- `GET /api/v1/search?q=&types=` шукає лише дозволені актору patient, appointment, payment і material objects; scope застосовується до match, ranking, limit і serialization.
- Ranking: exact identifier/code/phone → identifier prefix → name prefix → substring. PostgreSQL використовує `pg_trgm` і вісім targeted GIN indexes; Elasticsearch не потрібний.
- Responsive overlay підтримує `Ctrl/Cmd+K`, grouped loading/empty/error/retry states, keyboard navigation, `Escape`, focus return і body scroll lock.
- Canonical links відкривають patient route та appointment/payment/material details; query-param details відновлюються після reload і очищаються під час close.

## Automated gates

- canonical: `327/327` backend, `174/174` frontend, `36/36` axe;
- focused global-search backend: `29/29`;
- Ruff/format: `210` files; mypy: `163` source files;
- Django/OpenAPI snapshot/generated TypeScript schema, contracts, lint, strict typecheck і production build — green;
- security re-review: заборонені handlers/objects не викликаються й не серіалізуються; actionable findings відсутні.

## Migration, runtime і дані

Forward → reverse → forward gate відновив `pg_trgm` та всі вісім indexes. До й після циклу dev snapshot однаковий: OPEN shift `CSH-089CE5E936FC`; CARD payment `TXN-337279B7D390` на `390050`; payment/refund/cash-adjustment/ledger counts `1/0/0/1`; patients/appointments/materials `4/3/1`.

Runtime `/`, `/patients`, `/calendar`, `/finance`, `/inventory` і `/health/ready` повернув `200`; unauthenticated search — `401`.

Під час фінального read-only snapshot Docker Desktop bind-mount bridge дав `EIO` для `/app`. Після діагностики штатний Docker Desktop restart і точковий запуск попередніх контейнерів без видалення volumes/data відновили runtime; `manage.py check` повернув 0 issues, startup migration — `No migrations to apply`. Повторні routes і DB snapshot підтвердили ті самі статуси, counts та суми.

## Authenticated browser evidence

Desktop, `768×1024` tablet і `390×844` mobile показали три groups і чотири options для контрольного запиту. Перевірені keyboard lifecycle, `Ctrl/Cmd+K`, `Escape`, focus/body lock, exact patient route, reload-stable appointment/payment/material details, tablet без overflow, mobile fullscreen і controls щонайменше `44px`; console чиста.

- [Desktop grouped search](01-search-desktop-1440x900.png)
- [Payment deep link](02-payment-deep-link-desktop-1440x900.png)
- [Appointment deep link](03-appointment-deep-link-desktop-1440x900.png)
- [Material deep link](04-material-deep-link-desktop-1440x900.png)
- [Tablet grouped search](05-search-tablet-768x1024.png)
- [Mobile fullscreen search](06-search-mobile-390x844.png)
