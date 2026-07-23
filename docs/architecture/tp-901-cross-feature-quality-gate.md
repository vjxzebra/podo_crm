# TP-901 — cross-feature responsive, accessibility and resilience gate

Статус: frozen 2026-07-22. Packet не додає product features, API, models або migrations.

## 1. Межі

TP-901 повторно перевіряє завершені user-visible packets як одну систему:

- responsive shell і live routes на `1440×900`, `1024×768`, `390×844`;
- keyboard/focus, labels, landmarks, contrast, touch targets і internal scroll;
- loading/empty/filter/error/conflict/submitting/success/unsaved/offline/destructive/immutable/partial-widget states;
- read-only critical navigation journey без створення або зміни domain records.

Security/privacy hardening, зокрема expiry чинної session після початкового bootstrap, належить TP-902. Full podologist/reception/admin business UAT і 23/23 release acceptance належать TP-904.

## 2. Live route matrix

Authenticated admin route sweep охоплює:

`/`, `/calendar`, `/patients`, `/work-items`, `/finance`, `/finance/shifts`, `/inventory`, `/notifications`, `/audit`, `/analytics`, `/team`, `/settings`, `/password-resets`.

Для кожного route і viewport gate вимагає:

1. очікуваний `h1`, `main#main-content` і відсутність route-level alert;
2. `documentElement.scrollWidth <= clientWidth`; wide data може мати лише власний named/internal scroll;
3. нуль `console.error`, `console.warning` і uncaught page errors;
4. native axe без serious/critical WCAG A/AA violations, включно з реальним color contrast;
5. mobile shell замість sidebar на 390 px, tablet rail на 1024 px, desktop sidebar на 1440 px.

Representative visual baselines: overview, calendar, patients, finance, inventory і analytics на всіх трьох viewport.

## 3. Keyboard/focus journey

- перший `Tab` відкриває skip link; `Enter` переводить focus до `main#main-content`;
- `Ctrl+K` відкриває global search, focus переходить у query, `Escape` закриває overlay і повертає focus trigger;
- mobile «Ще» переводить focus у close control, блокує background scroll, `Escape` закриває sheet і повертає focus trigger;
- desktop navigation послідовно проходить overview → calendar → patients → finance → inventory → analytics → audit без direct URL або mutation;
- mobile bottom navigation проходить overview → calendar → patients, а protected secondary route відкривається через «Ще».

## 4. ST-01—ST-16 routing

| State | TP-901 proof |
|---|---|
| ST-01 loading | route/component skeletons; accessibility route sweep |
| ST-02 empty | overview/calendar/list/history/notification empty component tests і live empty states |
| ST-03 filtered empty | patient/finance/inventory/audit/analytics filter tests |
| ST-04 validation | appointment/visit/settings/inventory/finance form tests |
| ST-05 server error | calendar/search/notifications/audit/analytics/finance retry tests |
| ST-06 forbidden | role-safe direct-route redirect tests; TP-902 повторює security gate |
| ST-07 not found | indistinguishable patient/object not-found tests; TP-902 повторює IDOR gate |
| ST-08 conflict/stale | scheduling, visit, inventory, finance `409` recovery tests |
| ST-09 submitting/idempotent | pending-lock та stable-key tests для critical mutations |
| ST-10 success | authoritative refresh/success tests усіх mutation modules |
| ST-11 unsaved | appointment/visit/patient/settings/inventory/finance guards + axe |
| ST-12 offline/retry | exact mutation retry tests; TP-901 додає shell session-bootstrap recovery |
| ST-13 session expired | deferred to required TP-902 security/session hardening gate |
| ST-14 destructive confirm | cancel/deactivate/refund/stocktake/photo confirmation tests |
| ST-15 immutable | finance/shift/movement/audit detail tests і browser action audit |
| ST-16 partial widget | overview live data лишається доступним при незалежній work-items failure; analytics atomic projection має whole-response retry |

## 5. Exit criteria

- focused TP-901 component/browser tests green;
- canonical backend/frontend/OpenAPI/migration-free gates green;
- native responsive/axe/keyboard harness green і visual baselines збережені;
- runtime readiness/UI `200`, unauthenticated protected APIs `401`;
- відсутні undocumented product changes, domain mutations або secrets у tracked artifacts.
