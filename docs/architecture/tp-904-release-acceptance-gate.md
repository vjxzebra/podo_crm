# TP-904 — full-role UAT and 23/23 release acceptance gate

Дата фіксації: 2026-07-23. Джерела: [SPECIFICATION §21](../../SPECIFICATION.md),
[traceability matrix](../requirements/traceability-matrix.md), TP-901—TP-903 evidence.

## Межі пакета

TP-904 не додає business-функцій, API або migrations. Пакет повторно збирає й перевіряє
production candidate, зводить уже реалізовані вертикальні докази в один acceptance manifest,
виконує фінальний UAT для podologist/reception/admin і переводить AC-01—AC-23 у `verified`
лише після проходження всіх release gates. Post-MVP функції та provider-specific deployment
не входять до пакета.

## 23/23 acceptance manifest

- Кожен `AC-01`—`AC-23` має рівно один запис зі specification text, automated evidence,
  browser/operations evidence за потреби та фінальним `verified` status.
- `done` окремого task packet не замінює фінальний acceptance result. Відсутній файл,
  непройдений test, stale schema або непідтверджений role/viewport залишає критерій failed.
- AC-01 і AC-23 закриваються саме TP-904 full-role/full-viewport gate; AC-02—AC-22
  повторно звіряються з canonical regression suite та попередніми machine-readable evidence.
- Manifest не містить credentials, cookies, private object keys, patient contacts або
  інших sensitive fields.

## Role UAT

UAT використовує окремі локальні TP-904 fixtures і три session identities:

| Роль | Дозволені user surfaces | Обов'язковий negative gate |
|---|---|---|
| Podologist | overview, own calendar, scoped patients, own work items, notifications | finance/inventory/analytics/team/audit/settings direct URLs не відкривають protected content |
| Reception | overview, shared calendar, patients, work items, finance/shift history, notifications | inventory/analytics/team/audit/settings direct URLs не відкривають protected content |
| Admin | усі production surfaces, включно з inventory, analytics, team, audit, settings/access queue | чужий object ID не обходить selector/serializer scope; contract lab не є production business feature |

Кожна роль перевіряється на `1440×900`, `1024×768` і `390×844`. На кожному viewport
потрібні authenticated heading/shell, очікувана навігація, відсутність page overflow,
critical/serious axe violations та browser warning/error. Mobile використовує bottom nav і
fullscreen/sheet interaction; desktop/tablet — sidebar. Keyboard gate перевіряє skip link,
global search, `Escape`, focus return і role-safe navigation.

Live browser gate є read-only щодо clinical, inventory та finance domain data. Submit,
idempotency, concurrency, audit і rollback acceptance доводять canonical backend/component
tests; UAT відкриває та перевіряє відповідні forms, locked/read-only fields, summaries,
confirmation і error/retry states без проведення реальної медичної чи фінансової операції.

## Release candidate gates

1. Canonical backend і frontend profiles проходять повністю; OpenAPI snapshot/generated
   TypeScript schema, lint, strict typecheck, build, Ruff/format і mypy синхронні.
2. Fresh PostgreSQL застосовує всі migrations; populated dev DB має empty migration plan,
   valid constraints і проходить `verify_restore` object-reference gate.
3. Production Compose config не має source bind mounts; immutable backend/web candidate
   проходить `check --deploy`, migration job, root/readiness/session smoke `200/200/401`.
4. npm production audit, pip-audit і Docker Scout для runtime/ops images не мають
   critical/high findings. Accepted low advisories документуються окремо.
5. TP-903 encrypted restore, retention, deployment і image-only rollback evidence існує,
   parse-иться та має green result.

## Fixture і privacy policy

- UAT users створюються лише в `DEBUG` командою, що читає password із локального ignored
  file; password не передається як argument, не друкується й не потрапляє в evidence.
- Fixture records мають детермінований TP-904 marker і видаляються exact cleanup-командою
  після evidence. Cleanup не торкається інших users/domain records або persistent volumes.
- Screenshots не містять login form values, cookies, credentials або private object keys.

## Exit criteria

- `23/23` acceptance entries мають status `verified`, duplicate/missing IDs відсутні.
- Три ролі × три viewport пройшли role-route, responsive, accessibility і console gates.
- Canonical, migration, security, production candidate, restore і rollback gates green.
- UAT fixtures/sessions очищені, dev stack healthy, readiness `200`.
- Release checklist і machine-readable evidence збережені; planning/checkpoint documents
  переводять TP-904 і MVP M3 у `done` лише після фактичного проходження всього вище.
