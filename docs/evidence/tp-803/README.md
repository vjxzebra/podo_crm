# TP-803 — admin audit list/detail

Статус: `done` 2026-07-22.

## Реалізований зріз

- Admin-only `/audit` показує append-only журнал від найновішої події, пошук, фільтри працівника/розділу/точної дати та cursor pagination. Reception і podologist не отримують route у server session, а direct API access повертає `403`.
- Деталь відкривається через reload-stable `?event=<uuid>` незалежно від поточної сторінки списку й показує actor/role snapshot, час `Europe/Kyiv`, section/result, object reference, description, note/correlation ID та кожну redacted зміну як «Було → Стало».
- Object deep link з'являється лише для явно дозволених типів. Edit, delete та export actions відсутні; UI прямо позначає запис незмінним.
- Mobile detail є fullscreen dialog із body lock, focus trap, `Escape`, focus return і 44 px targets. На tablet список переходить у компактні картки.

## Automated gates

- canonical: `342/342` backend, `187/187` frontend і `38/38` axe scenarios;
- focused audit/access/session/notifications: `44/44` backend; focused Audit UI + accessibility: `44/44` frontend;
- Ruff/format, mypy, Django checks, OpenAPI snapshot/generated TypeScript schema, contracts, ESLint, strict typecheck і production build — green;
- registry-completeness test доводить, що всі `AuditAction` зареєстровані; redaction, append-only guards, date bounds, inverted range `422`, RBAC, detail retry, cursor та responsive keyboard lifecycle покриті tests.

## Migration і runtime

TP-803 є migration-free: `makemigrations --check --dry-run` повернув `No changes detected`, а `migrate --plan` — `No planned migration operations`. Django system check не виявив проблем.

Backend, web і proxy healthy. `/health/ready` та `/audit` повертають `200`; unauthenticated `GET /api/v1/audit-events` повертає `401`. Локальна БД містила 47 наявних append-only подій, тому evidence не створював і не змінював domain records.

## Authenticated browser evidence

На `1440×900`, `1024×768` і `390×844` перевірено admin navigation, list/detail, фільтр section `Склад` (`47 → 6`), reload-stable event URL, redacted «Було → Стало», allowlisted patient link, close focus return, mobile body lock та `Escape`. Browser gate виявив обрізання широких рядків на desktop/tablet і 42 px mobile close target; CSS виправлено, production image повторно зібрано, а фінальні метрики показали `scrollWidth ≤ width`, 44×44 close та відсутність page overflow. Console warnings/errors — `0`.

- [Desktop audit detail](audit-desktop.png)
- [Tablet compact audit](audit-tablet.png)
- [Mobile fullscreen diff](audit-mobile.png)
