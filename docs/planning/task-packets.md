# Вертикальні task packets Podoria CRM

## 1. Призначення

Цей реєстр розбиває MVP на невеликі інтегровані зміни, кожна з яких дає перевірюваний результат через backend, frontend і tests. Один packet розрахований на один PR і 1–2 дні активної роботи одного основного агента з паралельною підготовкою контракту та QA.

Джерела контракту в порядку пріоритету:

1. [`SPECIFICATION.md`](../../SPECIFICATION.md);
2. ADR зі статусом `Accepted` у [реєстрі рішень](../architecture/decisions/README.md);
3. [traceability matrix](../requirements/traceability-matrix.md) і [screen/state/access map](../requirements/screen-state-access-map.md);
4. прототип лише як візуальний орієнтир; відхилення контролює [prototype gap register](../requirements/prototype-gap-register.md).

## 2. Контракт виконання packet

Перед переходом `planned → ready` оркестратор фіксує точні OpenAPI schemas/examples, резервує migration у відповідному Django app і підтверджує залежності. Для всіх packet діють спільні правила:

- усі наведені endpoint paths мають префікс `/api/v1`, якщо явно не зазначено інше;
- error envelope: `code`, `message`, `fields`, `correlation_id`;
- час API — ISO 8601 UTC, UI — `Europe/Kyiv`; гроші — integer minor units;
- list/detail selectors застосовують role та object scope до serialization;
- кожна mutation має audit event у тій самій transaction; критична повторювана mutation — `Idempotency-Key`;
- UI обробляє loading, empty, validation, forbidden/not-found, conflict, retry та unsaved states, якщо вони можливі;
- acceptance evidence містить backend test, frontend/component test і Playwright для user-visible critical path;
- scope поза рядком `Не входить` потребує нового packet, а не прихованого розширення поточного PR.

Статуси: `planned`, `ready`, `in_progress`, `review`, `done`, `blocked`. ADR-залежні packet не можуть стати `ready`, доки ADR не має статусу `Accepted`.

| Packet | Поточний стан | Evidence / наступна дія |
|---|---|---|
| TP-101 | `done` | Compose config; 5 backend smoke tests; full stack healthy; live/readiness/proxy integration smoke |
| TP-102 | `done` | OpenAPI/error contract; generated client; backend/frontend quality gates; Docker CI test profile |
| TP-103 | `done` | Route/auth contracts; 14 component/a11y tests; responsive screenshots 1440×900, 768×1024, 390×844 |
| TP-201 | `done` | Email login/logout/session; centralized RBAC matrix; 31 backend + 16 frontend tests; direct-URL/browser evidence |
| TP-202 | `done` | Force-change session, own password, enumeration-safe forgot, admin reset queue/temp password, session revocation |
| TP-203—TP-904 | `planned` | Наступні: TP-203 team lifecycle або незалежний TP-207 audit infrastructure |

## 3. Володіння модулями

| Домен | Backend | Frontend | Основні tests |
|---|---|---|---|
| Platform/contracts | `backend/config`, root `infra/`, Compose/CI | `frontend/src/app`, generated client | `backend/tests/platform`, `frontend/e2e/smoke` |
| Accounts/team | `backend/apps/accounts` | `frontend/src/features/auth`, `team` | `backend/tests/security`, auth/team e2e |
| Clinic catalog | `backend/apps/clinic` | `frontend/src/features/settings` | clinic API/component e2e |
| Patients/workitems | `backend/apps/patients`, `workitems` | `frontend/src/features/patients`, `workitems` | patient/workitem API and e2e |
| Scheduling | `backend/apps/scheduling` | `frontend/src/features/calendar` | scheduling concurrency/API/e2e |
| Inventory | `backend/apps/inventory` | `frontend/src/features/inventory` | balance/locking/API/e2e |
| Visits | `backend/apps/visits` | `frontend/src/features/visits` | draft/finish/photo API/e2e |
| Billing | `backend/apps/billing` | `frontend/src/features/finance` | ledger/concurrency/API/e2e |
| Search/notifications | `backend/apps/search`, `notifications` | відповідні feature modules | role-scope/task idempotency/e2e |
| Audit/analytics | `backend/apps/audit`, `analytics` | відповідні feature modules | immutability/totals/API/e2e |

Лише інтегратор змінює root Compose/CI та регенерує TypeScript client. Агент не змінює сусідній домен без явної залежності в packet.

## 4. Backlog packet-ів

### Етап 1 — платформа

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-101 | Один Docker-запуск піднімає Django, PostgreSQL, Redis, Celery worker/beat, MinIO та web; план §5/етап 1 | `GET /health/live`, `GET /health/ready`; readiness перевіряє DB/Redis/object storage; JSON logs і request ID | Технічний unavailable screen; ролей ще немає; loading/retry | Залежностей немає. Доказ: Compose config, health integration, worker smoke. Не входить: business models |
| TP-102 | Відтворюваний quality/contract pipeline; план §3.5, §7 | `/api/v1/schema`; shared error envelope; OpenAPI → TypeScript client; Ruff, mypy, ESLint, strict TS, CI/test profile | Story/test page для success/error fixtures | TP-101. Доказ: clean clone CI, schema snapshot, generated-client compile. Не входить: domain endpoints |
| TP-103 | Responsive React shell і design tokens; SPEC §4, §18–19; AC-23 | Route registry і auth-boundary interface без client-side authorization claims | Desktop sidebar, tablet rail, mobile bottom nav; loading/empty/error/403/404 shells; prototype nav/previews | TP-102. Доказ: component/a11y tests і screenshots 1440×900, 768×1024, 390×844. Не входить: real session/data |

### Етап 2 — auth, команда й довідники

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-201 | Login/logout/session і централізований RBAC; SPEC §2–4; AC-01 | `POST /auth/login`, `POST /auth/logout`, `GET /session`; server session єдине джерело ролі; 401/403/404 scope policy | Login, logout, auth boundary, role-safe routes/menu; prototype `#loginScreen`; усі ролі | TP-101—103. Доказ: RBAC matrix, session rotation, direct-URL e2e. Не входить: role switcher у production |
| TP-202 | First login, own password change, forgot request і admin temporary password; SPEC §3; AC-21 | endpoints із traceability AC-21; current-password guard, force-change session, enumeration-safe forgot response, session revocation | Окремі own/admin forms, first-login block, reset queue/deep link; validation/loading/expired/success | TP-201. Доказ: policy/service/API/e2e. Не входить: email/SMS delivery |
| TP-203 | Team lifecycle; SPEC §12; AC-01, AC-21 | `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/deactivate`; fixed roles, unique login, last-admin protection | Admin list/create/edit/deactivate/temp password; reception/podologist hidden + 403 | TP-201—202, TP-207 contract. Доказ: last-admin/concurrency/RBAC/e2e. Не входить: custom permissions |
| TP-204 | Clinic profile й room catalog; SPEC §17.1; ADR-001 | `GET/PATCH /clinic-profile`, `GET/POST/PATCH /rooms`; one location, active room, historical snapshot | Admin settings; full phone/email/address; room empty/create/deactivate/conflict states | TP-201; ADR-001 `Accepted`. Доказ: validation/RBAC/e2e. Не входить: branches |
| TP-205 | Service catalog; SPEC §17.2 | `GET/POST /services`, `GET/PATCH /services/{id}`; unique code, non-negative price, positive duration, deactivation preserves history | Admin search/create/edit/color/active states; other roles read active picker projection only | TP-201, TP-207 contract. Доказ: model/API/component/e2e. Не входить: protocol templates |
| TP-206 | Eight status configs and clinic workdays/breaks; SPEC §6.9, §17.3–17.4 | `/appointment-status-configs`, `/clinic-workdays`; immutable system codes, valid non-overlapping breaks, clinic-wide only | Admin status/schedule settings; validation/unsaved states; no specialist schedule UI | TP-201; ADR-002 `Accepted`. Доказ: constraint/API/e2e. Не входить: holidays, vacations, exceptions |
| TP-207 | Append-only audit infrastructure usable by every later mutation; SPEC §14; AC-20 | internal audit service plus admin `GET /audit-events`, `GET /audit-events/{id}`; same transaction, redaction, no application update/delete | API fixtures only; full audit UI in TP-803 | TP-101—102, TP-201. Доказ: rollback/no-event, immutability, redaction, admin-only tests. Не входить: export/UI |

### Етап 3 — пацієнти й справи

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-301 | Patient list/search/create with duplicate warning; SPEC §7.1–7.3; AC-05 | `GET /patients?search=&cursor=`, `POST /patients`; normalized phone indexed but not unique; role selector before serializer | List/search/empty/inline create/duplicate warning; admin/reception all, podologist scoped | TP-201, TP-207. Доказ: normalization, scope/IDOR, API/component/e2e. Не входить: medical details |
| TP-302 | Patient card/edit із різними reception та medical projections; SPEC §7.4–7.7; AC-01 | `GET/PATCH /patients/{id}`, role-specific overview/history/photo metadata schemas; reception response не містить medical keys | Header/overview/history/photo shells; forbidden/not-found; prototype patient card | TP-301. Доказ: serialization absence, foreign-patient IDOR, edit audit, responsive e2e. Не входить: recommendations implementation |
| TP-303 | Внутрішні справи та «Перетелефонувати»; SPEC §5.4, §7.9 | `GET/POST /work-items`, `PATCH /work-items/{id}`; assignee scope, patient link, importance, due time, explicit completion | Overview tasks, create/complete, callback action; own/all scope by role | TP-301—302, TP-207. Доказ: scope/transition/API/e2e. Не входить: automatic phone calls |

### Етап 4 — календар і записи

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-401 | Day/week calendar та free-slot query; SPEC §6.1–6.3, §6.7; AC-03–04 | `GET /calendar`, `GET /appointments/availability`; working hours/breaks, specialist and room occupancy, role scope | Day/week, free/busy/loading/empty; concurrent cards; podologist own column | TP-204—206; ADR-001/002 `Accepted`. Доказ: selector/time-boundary/API/layout tests. Не входить: create mutation |
| TP-402 | Create appointment from CTA, slot, search and locked patient card; SPEC §6.4–6.7; AC-02, AC-05–07 | `POST /appointments`; complaint XOR, active patient/service/room, podologist-to-self, DB exclusion maps to `409 appointment_slot_conflict` | Patient search/inline create, locked patient, no-complaints, preserved form after errors | TP-301, TP-401. Доказ: three-role API/e2e and concurrent POST. Не входить: reschedule/status edit |
| TP-403 | Appointment detail/edit/reschedule/cancel/status workflow; SPEC §6.8–6.9; AC-03, AC-20 | `GET/PATCH /appointments/{id}`, transition actions; optimistic `version`, terminal guards, audit, cancellation reason | Details/edit/reschedule/status/cancel confirmation; 409 stale/slot conflicts | TP-402, TP-207. Доказ: transition table, concurrency, RBAC, e2e. Не входить: visit wizard |
| TP-404 | Calendar responsive/concurrent rendering gate; SPEC §19; AC-04, AC-23 | Без нового business API; контракт TP-401/403 | Desktop/tablet/mobile, horizontal specialist scroll, no text overlap, keyboard/touch/focus | TP-401—403. Доказ: visual snapshots + accessibility e2e. Не входить: new calendar features |

### Етап 5 — склад

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-501 | Material/lot catalog and details; SPEC §11.1–11.3 | `/inventory/materials`, `/inventory/materials/{id}`, `/lots`; unit immutable after movement, lot identity, expiry/available projections | Admin catalog/search/filter/details/lots; reception/podologist 403 | TP-201, TP-207. Доказ: model/API/RBAC/e2e. Не входить: supplier directory; supplier is lot/receipt attribute |
| TP-502 | Multi-line receipt and locked manual write-off; SPEC §11.4, §11.6; AC-19 | `POST /inventory/receipts`, `POST /inventory/write-offs`; idempotency, sorted lot locks, no negative balance, immutable posted rows | Admin receipt/write-off forms; availability, validation, conflict, success | TP-501. Доказ: rollback/idempotency/concurrent write-off/API/e2e. Не входить: stocktake |
| TP-503 | Stocktake, corrections and movement journal; SPEC §11.7–11.8; AC-19–20 | `POST /stocktakes`, `POST /stocktakes/{id}/post`, `GET /movements`; append-only compensation, cached balance reconciliation | Admin stocktake and journal/search/filter/detail; posted is read-only | TP-501—502. Доказ: reconciliation/property tests, immutability, API/e2e. Не входить: export unless separately approved |

### Етап 6 — прийом

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-601 | Start visit and persist examination draft; SPEC §8.1, §8.4, §8.7; AC-07–08 | `POST /appointments/{id}/start-visit`, `GET /visits/{id}`, `PUT /visits/{id}/draft`; one visit/appointment, assigned podologist/admin, versioned draft, no side effects | Wizard step 1, autosave/manual save, no-complaints, retry/unsaved | TP-302, TP-403. Доказ: role/transition/draft-no-side-effects/API/e2e. Не входить: service/material lines |
| TP-602 | Visit service quantities and material/lot usage draft; SPEC §8.2; AC-09 | Draft line contracts; service snapshots, unique line increments quantity, usable lot, quantity ≤ current projection; finish revalidates later | Wizard step 2 search/results/empty/quantity/remove/insufficient state | TP-205, TP-501, TP-601. Доказ: totals/dedup/search/API/component/e2e. Не входить: stock movement before finish |
| TP-603 | Private BEFORE/AFTER photo lifecycle; SPEC §7.7, §8.3; AC-10 | upload-intent/finalize/authorized-read/draft-delete endpoints; visit ownership, kind, limits, private signed URL | Separate dropzones, progress/preview/error/retry/delete; reception has no access | TP-601; ADR-004 `Accepted`. Доказ: MIME/size/count, IDOR/private bucket, cleanup, e2e. Не входить: completed delete UI |
| TP-604 | Atomic idempotent finish with inventory, receivable and optional follow-up; SPEC §8.4–8.6; AC-11–12, AC-18 | `POST /visits/{id}/finish`; lock order appointment→visit→lots; full rollback; one receivable; optional slot under same transaction; idempotency result | Wizard step 4 summary/recommendations/follow-up/send-to-payment; submitting/409/retry/success | TP-401, TP-502, TP-601—603. Доказ: fault injection, double submit, slot/stock races, e2e. Не входить: actual payment |
| TP-605 | Patient visit history, recommendations and photo carousel; SPEC §7.6–7.8; AC-08, AC-10 | visit history/recommendation endpoints; completed snapshot, author/date, medical role scope | Replace recommendations placeholder; history/photo carousel/loading/empty; reception-safe projection | TP-302, TP-603—604. Доказ: scope/serialization/API/component/e2e. Не входить: protocol templates |

### Етап 7 — фінанси й каса

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-701 | Open/current cash shift and ledger projection; SPEC §10.1–10.2 | `POST /cash-shifts`, `GET /cash-shifts/current`; one open shift per employee, ledger-derived totals | Reception/admin open/current shift; shift-required/already-open states | TP-207; ADR-006 `Accepted`. Доказ: partial unique, ownership, totals/API/e2e. Не входить: close/history |
| TP-702 | Full payment and finance operation list; SPEC §9.1–9.3; AC-13–14 | `GET /finance/operations`, `POST /payments`; amount server-derived, one payment/receivable, open shift, allowed method, idempotency | Search patient/unpaid visit, read-only total, filters/detail, already-paid/shift conflict | TP-604, TP-701; ADR-006 `Accepted`. Доказ: amount-schema assertion, concurrent payment, API/e2e. Не входить: partial/split payment |
| TP-703 | Full refund and cash deposit/withdrawal; SPEC §9.4–9.7; AC-14–15 | `POST /payments/{id}/refunds`, `POST /cash-movements`; full refund only, original method, no patient/method for adjustment, sufficient cash | Dedicated confirmation forms; reason/comment, available cash, conflict/success | TP-702; ADR-003/006 `Accepted`. Доказ: double refund, schema-negative, cash guard, API/e2e. Не входить: partial refund |
| TP-704 | Close/reconcile and role-scoped shift history; SPEC §10.3–10.5; AC-16–17 | `POST /cash-shifts/{id}/close`, `GET /cash-shifts`, `GET /cash-shifts/{id}`; owner/admin, counted confirmation, discrepancy comment, no reopen/new entries | Reception own history, admin all; close/detail/loading/empty/conflict | TP-701—703. Доказ: close/payment race, ledger reconciliation, RBAC/e2e. Не входить: export unless approved |

### Етап 8 — cross-domain read models

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-801 | Role-scoped global search and deep links; SPEC §16; AC-01, AC-22 | `GET /search?q=&types=`; normalized/trigram indexes; no forbidden category/object leakage | Search overlay, typing/loading/grouped/empty/error/create actions; role-safe canonical links | TP-301, TP-403, TP-503, TP-702. Доказ: role fixtures/IDOR/query plan/component/e2e. Не входить: Elasticsearch |
| TP-802 | Internal notifications, unread state and idempotent reminders; SPEC §15 | `GET /notifications`, `POST /notifications/{id}/read`, mark-all; scoped payloads, stable event key, Celery retry idempotency | Panel/filter/unread/empty/deep links/settings-safe fallback | Relevant domain events + TP-801 routing. Доказ: duplicate task, scope/redaction, API/e2e. Не входить: SMS/email/messengers |
| TP-803 | Admin audit list/detail «Було → Стало»; SPEC §14; AC-20 | Existing TP-207 endpoints with search/filter/cursor; redacted snapshots and stable object references | Admin-only list/detail/loading/empty/filter/deep link; other roles hidden + 403 | TP-207 plus all mutation event registries. Доказ: event coverage registry, redaction/RBAC/e2e. Не входить: edit/delete/export unless approved |
| TP-804 | Role overview projections and admin analytics; SPEC §5, §13 | `/overview`, `/analytics?from=&to=&specialist_id=`; totals derived from visits/ledger, role-scoped projections, stable date range | Replace hard-coded cards/charts; loading/empty/error/filter; podologist/reception/admin variants | Stable scheduling, visits, billing. Доказ: control dataset reconciliation, scope/API/e2e. Не входить: unapproved async export |

### Етап 9 — production gate

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-901 | Cross-feature responsive, accessibility and resilience sweep; SPEC §18–19; AC-23 | API unchanged; conflict/retry semantics frozen | Keyboard/focus/labels/contrast/touch; all critical loading/empty/error/offline/unsaved states on three viewports | All user-visible packets. Доказ: axe, visual regression and critical journey e2e. Не входить: new features |
| TP-902 | Security/privacy hardening; SPEC §2.4, §3, §14, §20 | Login rate limit, session expiry, headers, upload validation, selector/serializer IDOR defense, secret redaction | Safe expired-session/403/404/retry behavior without data leakage | All domains; ADR-004 `Accepted`. Доказ: security suite and zero critical/high findings. Не входить: external SSO |
| TP-903 | Backup/restore, deployment and rollback rehearsal | Operational endpoints/runbooks; off-host encrypted backups, retention, RPO/RTO, migration order | Admin has no direct backup UI requirement | TP-101 and stable schema; ADR-005 `Accepted`. Доказ: isolated restore drill, smoke, rollback checklist. Не входить: provider-specific product feature |
| TP-904 | Full role UAT and 23/23 acceptance release gate; SPEC §21 | Frozen OpenAPI, migration from empty/populated DB, production health/readiness | Podologist/reception/admin journeys desktop/tablet/phone | TP-901—903 and all AC packets. Доказ: traceability suite 23/23, signed UAT, release checklist. Не входить: post-MVP backlog |

## 5. Покриття acceptance criteria

| AC | Primary packet | Обов’язковий інтеграційний gate |
|---|---|---|
| AC-01 | TP-201, TP-302 | TP-902, TP-904 |
| AC-02 | TP-402 | TP-404, TP-904 |
| AC-03 | TP-401—403 | TP-904 |
| AC-04 | TP-401, TP-404 | TP-901 |
| AC-05 | TP-301, TP-402 | TP-904 |
| AC-06 | TP-402 | TP-904 |
| AC-07 | TP-402, TP-601 | TP-904 |
| AC-08 | TP-601—605 | TP-904 |
| AC-09 | TP-602 | TP-604 |
| AC-10 | TP-603, TP-605 | TP-902 |
| AC-11 | TP-604 | TP-702, TP-904 |
| AC-12 | TP-604 | TP-904 |
| AC-13 | TP-702 | TP-904 |
| AC-14 | TP-702—703 | TP-904 |
| AC-15 | TP-703 | TP-904 |
| AC-16 | TP-704 | TP-904 |
| AC-17 | TP-704 | TP-904 |
| AC-18 | TP-502, TP-604 | TP-904 |
| AC-19 | TP-502—503 | TP-904 |
| AC-20 | TP-207, TP-803 | TP-904 |
| AC-21 | TP-202—203 | TP-902 |
| AC-22 | TP-801 | TP-902 |
| AC-23 | TP-103, TP-404, TP-901 | TP-904 |

## 6. Порядок найближчого запуску

ERD та ADR-001—ADR-006 погоджені 2026-07-20; TP-101—TP-103, TP-201 і TP-202 завершено. Наступним можна вести TP-203 team lifecycle або незалежний TP-207 audit infrastructure. Password lifecycle тепер зафіксований typed API та session policy; базовий RBAC уже відкрив залежні довідники й домени, а inventory TP-501—503 може йти паралельно з TP-301—404 після append-only audit infrastructure.
