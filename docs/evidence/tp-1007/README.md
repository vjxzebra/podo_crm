# TP-1007 — безпечний CSV export журналу дій

Статус: `done` 2026-07-23.

## Реалізований scope

- `GET /api/v1/audit-events/export` використовує ті самі queryset filters і
  stable ordering `occurred_at DESC, id DESC`, що й журнал дій, але без
  pagination.
- Admin-only CSV приймає рівно п’ять applied filters, має UTF-8 BOM,
  RFC 4180 quoting, CRLF, `no-store`, server filename,
  `X-Export-Event-Count` і `X-Export-Row-Count`. Hard bounds — `5000` подій та
  `366` днів без partial response.
- Stable 28-column report завжди починається з `REPORT_SUMMARY`, включно з
  empty result, містить totals усіх 11 audit sections і далі deterministic
  `AUDIT_EVENT` rows.
- Report не містить actor email/ID, object ID, `before`, `after`, `changes`,
  note, correlation ID, clinical/security payload або raw snapshots. Усі text
  cells проходять NUL/formula sanitizer.
- Admin CTA `Експортувати CSV` використовує лише останній applied query,
  блокується під час initial/reload/list-error/export-pending state, приймає
  server filename і показує success/error/retry без приховування filters,
  event list чи detail. Reception і podologist не мають route або CTA.

## Автоматизовані gates

- Focused backend: `6/6` — summary/counts/order/privacy/no-audit-mutation,
  exact five-filter parity, empty report, RBAC/range/unsupported query,
  row-bound/no-partial та NUL-before-formula safety.
- Focused frontend: `8/8` `AuditPage` scenarios, включно з applied
  query/pending/server filename/content preservation, error/retry та
  відсутністю CTA для reception.
- Canonical: `407/407` backend, `213/213` frontend, `40/40` axe.
- Ruff і formatter перевірили `258` Python files; mypy — `194` source files.
  Django checks, migrations, OpenAPI snapshot, generated TypeScript schema,
  contracts, ESLint, strict typecheck, production build і production `web`
  image — green.

## Live HTTP

Memory-only authenticated admin probe з applied `section`, `date_from` і
`date_to` підтвердив:

- CSRF bootstrap `401` очікувано встановив cookie, login `200`, export `200`;
- `text/csv; charset=utf-8`, `audit-events-…csv`,
  `Cache-Control: no-store`;
- UTF-8 BOM, CRLF, `28` columns, first row `REPORT_SUMMARY`;
- `X-Export-Event-Count: 1`, `X-Export-Row-Count: 2` і рівно `2` parsed data
  rows;
- query містив лише три applied filter keys;
- header збігся зі stable schema, forbidden columns були відсутні.

Credentials читалися лише з Git-ignored `.env.local`, не потрапляли в output,
а CSV не записувався на диск. Endpoint не створив domain або audit mutations.

## Responsive browser QA

Authenticated in-app browser підтвердив success state, збереження filters,
event list і detail, а також чисту console на трьох viewport:

- `1440×1000`: CTA `141.65×44px`, `0` horizontal overflow, success і
  `48 завантажено` лишилися видимими;
- `768×1024`: CTA `141.65×44px`, `0` horizontal overflow, heading, filters,
  event cards і detail присутні;
- `390×844`: CTA `351×44px`, `0` horizontal overflow, full-width action,
  filters і success присутні.

Console gate: `0` warnings/errors. Viewport скинуто через authoritative
`reset()`, browser tabs закрито.

Артефакти:

- [desktop success](desktop-audit-export-success.png)
- [tablet success](tablet-audit-export-success.png)
- [mobile success](mobile-audit-export-success.png)

## Runtime recovery

Перший focused backend запуск не побачив нові файли. Compose inspection
підтвердив, що `backend-test` навмисно працює з immutable image без bind mount,
тоді як dev backend mount уже містив зміни. Точково перебудовано лише
`backend-test`, після чого visibility probe і всі `6/6` tests пройшли.

Ручний mypy без canonical `--no-sqlite-cache` отримав internal traceback через
відсутній `sqlite3` у stripped test runtime. Перевірка
`backend/scripts/check.sh` підтвердила штатний прапорець; повторний canonical
mypy із ним пройшов `194` source files.

У canonical wrapper паралельний frontend ESLint один раз завершився V8
`Fatal JavaScript invalid array length`, поки backend продовжив і пройшов
`407/407`. Перевірено ресурси та відсутність залишкових test containers;
повний frontend gate окремо пройшов `213/213`, `40/40` axe і production build.

Під час production `web` build integrated BuildKit також отримав V8
`SIGSEGV`, а Docker daemon не дочекався exit event старого backend container.
Compose/daemon state перевірено, штатний restart Docker Desktop відновив
керування containers, а `docker compose up -d --wait` повернув readiness
`200` без видалення volumes. `web` потім успішно зібрано через ізольований
builder `podoria-tp701-recovery`, завантажено в local image store, точково
recreate-нуто й перевірено через актуальний asset та `200` root/readiness.

Перші live HTTP probes окремо виявили дві помилки harness: parser очікував
headers до status line, а login не мав CSRF bootstrap. Parser виправлено;
попередній `GET /api/v1/session` встановив CSRF cookie, після чого memory-only
authenticated probe пройшов повністю. Це не вимагало змін endpoint або даних.

## Final hygiene

- `git diff --check` — green; TP-1007 files не мають trailing whitespace.
- Stale TP-1007 `in_progress` markers — `0`; усі три screenshot artifacts
  присутні.
- `.env.local` ігнорується Git; tracked збігів реального локального пароля —
  `0`. Локальний admin email дорівнює безпечному placeholder з `.env.example`.
- Readiness — `200`; test containers після gates — `0`; production
  proxy/backend/web і stateful services healthy, `minio-init` завершився `0`.
