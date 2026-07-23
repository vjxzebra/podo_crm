# TP-804 — role overview and admin analytics

Статус: `done` 2026-07-22.

## Реалізований зріз

- `GET /api/v1/overview?date=YYYY-MM-DD` формує live projection для admin, reception і podologist. Подолог бачить лише власний розклад/пацієнтів/справи без фінансів; reception — clinic schedule, net payments, спеціалістів і unpaid; admin — clinic schedule, catalog-price expected income та attention counters.
- Admin-only `GET /api/v1/analytics?from=&to=&specialist_id=&service_id=` використовує inclusive дати `Europe/Kyiv`, ліміт 366 днів і повертає KPI, trend, appointment outcomes, specialist utilization та service ranking. Reception/podologist отримують `403`.
- Чистий виторг звіряється як payments мінус refunds; deposit/withdrawal не входять. Average check — net revenue / payment count. Service ranking читає immutable visit-line snapshots, а utilization — scheduled minutes / clinic working minutes без configured breaks.
- `/` більше не показує prototype/demo numbers. `/analytics` має month/quarter/year/custom period, specialist/service filters, loading/empty/error/retry states і автоматично перебудовує всі панелі. Непогодженого export CTA немає.

## Automated gates

- canonical: `345/345` backend, `192/192` frontend і `39/39` axe scenarios;
- focused TP-804: `3/3` backend API та `4/4` frontend component tests;
- Ruff, mypy (`180` source files), Django check, OpenAPI validation/snapshot, generated TypeScript schema, contracts, ESLint, strict typecheck і production build — green;
- control dataset звіряє ledger refunds, cohorts, average interval, outcomes, immutable service ranking, specialist filter і utilization denominator; окремі tests покривають role projections, RBAC та invalid ranges.

## Migration і runtime

TP-804 є migration-free: `makemigrations --check --dry-run` повернув `No changes detected`, а `migrate --plan` — `No planned migration operations`.

Backend, web і proxy healthy; `/health/ready` повертає `200`. Authenticated local admin отримав live overview та analytics із наявних dev records. Quarter filter змінив range `2026-07-01 → 2026-09-30` і periodization з days на weeks. Browser console warnings/errors — `0`; runtime gate не створював і не змінював domain records.

Під час production build необмежений Vitest forks pool аварійно завершив один Node 24/V8 worker. Ресурси Docker були достатні, focused test пройшов, а повний suite стабільно відтворився з двома workers. `maxWorkers: 2` зафіксовано у `frontend/vite.config.ts`; штатний Docker `npm run check` після цього пройшов `192/192` і production image успішно перебудовано.

## Authenticated responsive browser evidence

Native Edge harness перевірив `/` і `/analytics` на `1440×900`, `1024×768` і `390×844`: adaptive grids/shell, 6 KPI, server-backed quarter refetch, table internal scroll, відсутність page overflow та export CTA. In-app browser окремо підтвердив canonical navigation, реальні локальні значення, empty overview state й чисту console.

- [Desktop overview](overview-desktop.png)
- [Tablet overview](overview-tablet.png)
- [Mobile overview](overview-mobile.png)
- [Desktop analytics](analytics-desktop.png)
- [Tablet analytics](analytics-tablet.png)
- [Mobile analytics](analytics-mobile.png)
