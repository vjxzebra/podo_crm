# TP-901 — cross-feature responsive, accessibility and resilience sweep

Статус: `done` 2026-07-22.

## Покритий зріз

- Read-only admin sweep охопив 13 критичних маршрутів: `/`, `/calendar`, `/patients`, `/work-items`, `/finance`, `/finance/shifts`, `/inventory`, `/notifications`, `/audit`, `/analytics`, `/team`, `/settings`, `/password-resets`.
- Кожен маршрут перевірено у native Microsoft Edge на `1440×900`, `1024×768` і `390×844`: разом 39 route×viewport checks, без page overflow, browser warnings/errors або axe WCAG A/AA violations.
- Mobile gate перевіряє первинні touch targets `≥44×44`, правильне перемикання sidebar/bottom navigation та внутрішній scroll замість page overflow.
- Keyboard journey підтверджує перший `Tab` → skip link → `main`, `Ctrl+K` → global search → `Escape`/focus return, desktop navigation через шість модулів та modal lifecycle mobile «Ще» з body lock/focus return.
- Representative visual baseline збережено для overview, calendar, patients, finance, inventory й analytics на всіх трьох viewport — 18 PNG.

## Виправлені дефекти

- системні muted/subtle та coral text tokens доведено до AA contrast; окремо виправлено підпис вільного calendar slot;
- scrollable analytics chart і дві mobile tables отримали keyboard focus, accessible region names та visible focus rings;
- compact tablet profile button отримала viewport-independent accessible name;
- базові primary/icon controls і локальні calendar/patients/tasks targets доведено до 44 px;
- skip-link тепер фактично фокусує `main#main-content` через `tabIndex={-1}`;
- спільний modal lifecycle блокує background scroll, traps focus і відновлює focus для global search та mobile More;
- додано shell session-bootstrap offline/retry та partial overview-widget regression tests;
- role-fallback mocks notifications/audit тепер повертають валідну overview projection і не приховують route regressions.

## Automated gates

- canonical Docker gate: `345/345` backend і `194/194` frontend;
- frontend axe component suite: `39/39` scenarios;
- Ruff format/check, mypy для `180` source files, Django check/migrations, OpenAPI snapshot/generated client, contracts, ESLint, strict TypeScript і production build — green;
- native Edge gate: `39/39` route×viewport, `0` axe violations, `0` browser warnings/errors, `0` page-overflow або undersized-primary-target failures;
- focused resilience tests: `2/2`; targeted modal/search/app regressions: `96/96`.

TP-901 не змінює API, models, migrations або business rules і не виконує domain mutations. Session-expiry/security hardening лишається обов’язковим TP-902; full role UAT і release acceptance — TP-904.

## Migration і runtime

`makemigrations --check --dry-run` повернув `No changes detected`, `migrate --plan` — `No planned migration operations`. Фінальний production image пройшов повний frontend check в ізольованому docker-container builder після того, як інтегрований BuildKit executor двічі завершив ESLint із локальним `SIGSEGV`; звичайний container lint, RAM/disk і canonical gate були здорові. `web`, backend і proxy healthy; `/`, `/analytics` та `/health/ready` повертають `200`, unauthenticated analytics API — `401`.

## Evidence

- [Machine-readable browser gate](browser-gate.json)
- Overview: [desktop](overview-desktop.png), [tablet](overview-tablet.png), [mobile](overview-mobile.png)
- Calendar: [desktop](calendar-desktop.png), [tablet](calendar-tablet.png), [mobile](calendar-mobile.png)
- Patients: [desktop](patients-desktop.png), [tablet](patients-tablet.png), [mobile](patients-mobile.png)
- Finance: [desktop](finance-desktop.png), [tablet](finance-tablet.png), [mobile](finance-mobile.png)
- Inventory: [desktop](inventory-desktop.png), [tablet](inventory-tablet.png), [mobile](inventory-mobile.png)
- Analytics: [desktop](analytics-desktop.png), [tablet](analytics-tablet.png), [mobile](analytics-mobile.png)
