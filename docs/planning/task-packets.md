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
| TP-203 | `done` | Admin team list/create/edit/reactivate/deactivate/temp password; fixed roles; session revocation; concurrent last-admin guard; audit; responsive evidence |
| TP-204 | `done` | Singleton clinic profile; private validated logo; one-location room catalog; optimistic conflicts; audit/RBAC; responsive Edge evidence |
| TP-205 | `done` | Service CRUD without delete; unique code/domain constraints; admin catalog/palette/conflicts; active picker projection; audit/RBAC; responsive Edge evidence |
| TP-206 | `done` | 8 protected status configs; atomic 7-day clinic schedule/breaks; optimistic conflicts; audit/RBAC; responsive UI |
| TP-207 | `done` | UUID event registry; same-transaction service; recursive secret redaction; model/queryset + PostgreSQL append-only guards; admin list/detail API |
| TP-301 | `done` | Normalized-phone patient model; scoped live search; cursor pagination; duplicate warning; atomic audit; responsive list/create UI |
| TP-302 | `done` | Role-safe patient card/edit; reception-safe та medical projections; scoped IDOR; atomic edit audit; responsive overview/history/photo shells |
| TP-303 | `done` | Scoped internal work items; linked patient/assignee validation; versioned complete/reopen; atomic audit; responsive list/create/callback UI |
| TP-401 | `done` | Appointment time ranges; specialist/room exclusion constraints; role-scoped calendar/availability; day/week responsive UI; 134 backend + 58 frontend tests; browser evidence |
| TP-402 | `done` | Transactional appointment create; role/patient/resource/complaint checks; concurrent specialist/room conflict mapping; CTA/slot/locked patient/inline create UI; 143 backend + 64 frontend tests; browser evidence |
| TP-403 | `done` | Role-scoped detail; versioned edit/reschedule/status/cancel; terminal/visit guards; required cancellation reason; atomic audit; responsive dialog; 153 backend + 68 frontend tests; browser evidence |
| TP-404 | `done` | Desktop/tablet/mobile day/week gate; named internal scroll; 44px tablet/mobile targets; concurrent no-overlap/text-clipping checks; keyboard/dialog focus lifecycle; 153 backend + 70 frontend tests; browser evidence |
| TP-501 | `done` | Material CRUD без delete; lot identity/unit invariants; expiry/available/FEFO projections; admin catalog/details; 161 backend + 75 frontend tests; responsive browser evidence |
| TP-502 | `done` | Idempotent multi-line receipt; sorted row locks; locked no-negative manual write-off; immutable operations/movements; atomic audit; 170 backend + 81 frontend tests; responsive browser evidence |
| TP-503 | `done` | Immutable stocktake draft/post; stale-balance rejection; append-only corrections; filtered movement journal/detail; atomic audit; 183 backend + 86 frontend tests; responsive browser evidence |
| TP-601 | `done` | Idempotent ARRIVED→IN_PROGRESS start; one visit/appointment; assigned podologist/admin scope; versioned examination draft without stock/finance/completion side effects; 192 backend + 92 frontend tests; responsive browser evidence |
| TP-602 | `done` | Snapshot service/material/lot draft lines; quantities/totals/dedup; scoped FEFO picker; no stock side effects; 201 backend + 98 frontend tests; responsive browser evidence |
| TP-603 | `done` | Private BEFORE/AFTER upload-intent/finalize/read/delete; canonical EXIF-free images; signed role/object access; cleanup/audit; 208 backend + 103 frontend tests; responsive browser evidence |
| TP-604 | `done` | Atomic idempotent finish; appointment→visit→sorted-lot locks; VISIT_USAGE, receivable, recommendation, optional follow-up, rollback/race gates; 218 backend + 106 frontend tests; responsive browser evidence |
| TP-605 | `done` | Role-safe completed history; visit-grouped private popup carousel; versioned authored recommendations/audit; 226 backend + 117 frontend tests, 28 axe scenarios; responsive browser evidence |
| TP-701 | `done` | Own open/current cash shift; one-open concurrency guard; ledger-derived projection; DB/model/admin immutability; atomic audit; 248 backend + 127 frontend tests, 30 axe scenarios; responsive browser evidence |
| TP-702 | `done` | Paid+unpaid union one-row-per-Receivable; full-payment POST без amount; own OPEN shift, idempotency, atomic audit і zero auto-settlement; 266 backend + 137 frontend tests, 32 axe scenarios; responsive read-only browser evidence |
| TP-703 | `done` | Full server-derived refund, strict cash movements, tagged projection, idempotency/concurrency/audit/DB invariants; 284 backend + 151 frontend tests, 35 axe scenarios; [responsive read-only evidence](../evidence/tp-703/README.md) |
| TP-704 | `done` | [Frozen close/history contract](../architecture/tp-704-cash-shift-close-history-contract.md); versioned close/history, contracts, migration/runtime і responsive read-only browser gates green: 298 backend, 164 frontend, 35 axe; [evidence](../evidence/tp-704/README.md) |
| TP-801 | `done` | Role-scoped patient/appointment/payment/material search, canonical deep links, `pg_trgm` + 8 GIN indexes; 327 backend, 174 frontend, 36 axe; [evidence](../evidence/tp-801/README.md) |
| TP-802 | `done` | Recipient-scoped internal notifications, unread/count/read-all, safe deep links, idempotent domain events і Celery beat reminders; 340 backend, 180 frontend, 37 axe; [evidence](../evidence/tp-802/README.md) |
| TP-803 | `done` | Admin-only list/detail «Було → Стало», registry/redaction/RBAC/contracts і responsive runtime gate; 342 backend, 187 frontend, 38 axe; [evidence](../evidence/tp-803/README.md) |
| TP-804 | `done` | Role-scoped live overview та admin-only ledger/visit analytics; filters/contracts/migration-free runtime і responsive gates; 345 backend, 192 frontend, 39 axe; [evidence](../evidence/tp-804/README.md) |
| TP-901 | `done` | Cross-feature Edge/axe/keyboard/resilience sweep: 13 routes × 3 viewport, 18 baselines, 345 backend, 194 frontend, 39 axe; [evidence](../evidence/tp-901/README.md) |
| TP-902 | `done` | Login rate limit, idle/absolute expiry, headers/cache policy, canonical logo validation, redaction/IDOR regression, clean dependency audits; 352 backend, 198 frontend, 40 axe; [evidence](../evidence/tp-902/README.md) |
| TP-903 | `done` | Encrypted off-host recovery points, 30/12 retention, isolated restore, immutable deploy/image-only rollback, 0C/0H ops image; 357 backend, 198 frontend, 40 axe; [evidence](../evidence/tp-903/README.md) |
| TP-904 | `done` | 23/23 acceptance; 3 roles × 3 viewport, 75 route checks, 11 forbidden redirects, canonical 364 backend/198 frontend/40 axe, database/dependency/image/production gates green; [evidence](../evidence/tp-904/README.md) |
| TP-1001 | `done` | Supplier directory, legacy lot linkage і receipt picker; 372 backend/200 frontend/40 axe та responsive evidence green; [evidence](../evidence/tp-1001/README.md) |
| TP-1002 | `done` | Filtered admin inventory movement CSV; 380 backend/202 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1002/README.md) |
| TP-1003 | `done` | Exact cash-shift detail CSV; 385 backend/204 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1003/README.md) |
| TP-1004 | `done` | Filtered cash-shift history summary CSV; 390 backend/206 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1004/README.md) |
| TP-1005 | `done` | Aggregate admin analytics CSV; 395 backend/208 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1005/README.md) |
| TP-1006 | `done` | Filtered admin finance-operation CSV; 401 backend/211 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1006/README.md) |
| TP-1007 | `done` | Filtered admin audit journal CSV; 407 backend/213 frontend/40 axe, live HTTP і responsive browser evidence green; [evidence](../evidence/tp-1007/README.md) |
| TP-1008 | `done` | Role-scoped CRM register і idempotent process workflow; optional client name/phone/service/comment; 426 backend/223 frontend/42 axe, role/responsive/optional-field browser QA green; [evidence](../evidence/tp-1008/README.md) |
| TP-1009 | `done` | Digest-only Bearer token rotation, external idempotent create API та [integration guide](../integrations/booking-requests-api.md); 434 backend/225 frontend/42 axe, live HTTP і responsive browser gates green; [evidence](../evidence/tp-1009/README.md) |
| TP-1010 | `planned` | Додати one-time Telegram linking, verified webhook і durable fan-out; залежить від TP-1009 |
| TP-1011 | `planned` | Додати authorized process callback, cross-chat message sync/retry та production rollout; залежить від TP-1010 і нового bot token |

## 3. Володіння модулями

| Домен | Backend | Frontend | Основні tests |
|---|---|---|---|
| Platform/contracts | `backend/config`, root `infra/`, Compose/CI | `frontend/src/app`, generated client | `backend/tests/platform`, `frontend/e2e/smoke` |
| Accounts/team | `backend/apps/accounts` | `frontend/src/features/auth`, `team` | `backend/tests/security`, auth/team e2e |
| Clinic catalog | `backend/apps/clinic` | `frontend/src/features/settings` | clinic API/component e2e |
| Patients/workitems | `backend/apps/patients`, `workitems` | `frontend/src/features/patients`, `workitems` | patient/workitem API and e2e |
| Scheduling | `backend/apps/scheduling` | `frontend/src/calendar` | scheduling concurrency/API/e2e |
| Inventory | `backend/apps/inventory` | `frontend/src/features/inventory` | balance/locking/API/e2e |
| Visits | `backend/apps/visits` | `frontend/src/features/visits` | draft/finish/photo API/e2e |
| Billing | `backend/apps/billing` | `frontend/src/features/finance` | ledger/concurrency/API/e2e |
| Search/notifications | `backend/apps/search`, `notifications` | відповідні feature modules | role-scope/task idempotency/e2e |
| Audit/analytics | `backend/apps/audit`, `analytics` | відповідні feature modules | immutability/totals/API/e2e |
| Booking requests/Telegram | `backend/apps/booking_requests` | `frontend/src/booking-requests`, profile/settings integration UI | RBAC/idempotency/webhook/delivery/a11y/e2e |

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
| TP-601 | Start visit and persist examination draft; SPEC §8.1, §8.4, §8.7; AC-07–08 | `POST /appointments/{id}/start-visit`, `GET /visits/{id}`, `PUT /visits/{id}`; one visit/appointment, assigned podologist/admin, versioned draft, no side effects | Wizard step 1, autosave/manual save, no-complaints, retry/unsaved | TP-302, TP-403. Доказ: role/transition/draft-no-side-effects/API/e2e. Не входить: service/material lines |
| TP-602 | Visit service quantities and material/lot usage draft; SPEC §8.2; AC-09 | Draft line contracts; service snapshots, unique line increments quantity, usable lot, quantity ≤ current projection; finish revalidates later | Wizard step 2 search/results/empty/quantity/remove/insufficient state | TP-205, TP-501, TP-601. Доказ: totals/dedup/search/API/component/e2e. Не входить: stock movement before finish |
| TP-603 | Private BEFORE/AFTER photo lifecycle; SPEC §7.7, §8.3; AC-10 | upload-intent/finalize/authorized-read/draft-delete endpoints; visit ownership, kind, limits, private signed URL | Separate dropzones, progress/preview/error/retry/delete; reception has no access | TP-601; ADR-004 `Accepted`. Доказ: MIME/size/count, IDOR/private bucket, cleanup, e2e. Не входить: completed delete UI |
| TP-604 | Atomic idempotent finish with inventory, receivable and optional follow-up; SPEC §8.4–8.6; AC-11–12, AC-18 | `POST /visits/{id}/finish`; lock order appointment→visit→lots; full rollback; one receivable; optional slot under same transaction; idempotency result | Wizard step 4 summary/recommendations/follow-up/send-to-payment; submitting/409/retry/success | TP-401, TP-502, TP-601—603. Доказ: fault injection, double submit, slot/stock races, e2e. Не входить: actual payment |
| TP-605 | Patient visit history, recommendations and photo carousel; SPEC §7.6–7.8; AC-08, AC-10 | `GET /patients/{id}/{visits\|photos\|recommendations}` і visit-scoped recommendation POST/GET/PATCH; completed snapshots, cursor, signed photo URLs, version/audit, medical own-scope | Role-safe history; grouped «До / Після» popup carousel; authored recommendation add/edit/conflict; loading/empty/error/retry/unsaved | TP-302, TP-603—604. Доказ: scope/serialization/API/component/a11y/browser. Не входить: protocol templates |

### Етап 7 — фінанси й каса

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-701 | Open/current cash shift and ledger projection; SPEC §10.1–10.2 | `POST /cash-shifts`, `GET /cash-shifts/current`; one open shift per employee, ledger-derived totals | Reception/admin open/current shift; shift-required/already-open states | TP-207; ADR-006 `Accepted`. Доказ: partial unique, ownership, totals/API/e2e. Не входить: close/history |
| TP-702 | Full payment and finance operation list; SPEC §9.1–9.3; AC-13–14; [frozen contract](../architecture/tp-702-finance-contract.md) | `GET /finance/operations` — one row per Receivable paid/unpaid union; `POST /payments` приймає лише `visit_id`, `payment_method`, optional `comment`; full amount server-derived, one payment/receivable, own open shift, idempotency; zero total auto-settles without ledger | Search patient/unpaid visit, read-only total, filters/embedded detail, full-payment dialog, already-paid/shift conflict; no custom amount; desktop/tablet/mobile | TP-604, TP-701; ADR-006 `Accepted`. Доказ: amount-schema assertion, concurrent payment, audit/rollback, API/component/a11y та read-only browser evidence. Не входить: partial/split payment, refund/cash adjustments, close/history |
| TP-703 | Full refund and cash deposit/withdrawal; SPEC §9.4–9.7; AC-14–15; [frozen contract](../architecture/tp-703-refund-cash-contract.md) | `POST /payments/{id}/refunds`, `POST /cash-movements`; full refund only, original method, strict cash-adjustment schema, current actor shift, sufficient cash, shared cash-movement idempotency family | Dedicated confirmation forms; refundable picker, reason/comment, read-only refund amount/method, available cash, conflict/success | `done` 2026-07-22; TP-702; ADR-003/006 `Accepted`. Double/concurrent/cross-shift refund, schema-negative, cash guard, API/component/a11y/browser gates пройшли: 57 billing, 18 TP-703, 284 backend, 151 frontend, 35 axe; [evidence](../evidence/tp-703/README.md). Не входить: partial refund, close/history |
| TP-704 | Close/reconcile and role-scoped shift history; SPEC §10.3–10.5; AC-16–17; [frozen contract](../architecture/tp-704-cash-shift-close-history-contract.md) | `GET /cash-shifts/{id}/close-preview`, `POST /cash-shifts/{id}/close`, `GET /cash-shifts`, `GET /cash-shifts/{id}`; owner/admin, revision check, exact idempotent replay, ledger-derived reconciliation, immutable CLOSED | Reception own history, admin all; `/finance/shifts`, close/detail/loading/empty/stale/conflict/retry, responsive table/cards | `done` 2026-07-22: 71 billing, 14 TP-704, 298 backend, 164 frontend і 35 axe пройшли; migration cycle та dev-data preservation green; authenticated desktop/tablet/mobile browser gate підтвердив close dialog без submit, history/detail, 0 overflow, 44 px targets і clean console. [Evidence](../evidence/tp-704/README.md). Live close не виконувався. Не входить: export/reopen/edit/delete |

### Етап 8 — cross-domain read models

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-801 | Role-scoped global search and deep links; SPEC §16; AC-01, AC-22 | `GET /search?q=&types=`; scope before match/rank/limit/serialization; exact/prefix/substring ranking; `pg_trgm` + 8 targeted GIN indexes; no forbidden category/object leakage | Responsive overlay, typing/loading/grouped/empty/error/retry/create actions; keyboard/focus/body-lock lifecycle; role-safe patient/appointment/payment/material links | `done` 2026-07-22: 29 focused search, 327 backend, 174 frontend і 36 axe tests; contracts, migration reverse/reapply, query plans, runtime і authenticated desktop/tablet/mobile gates green; [evidence](../evidence/tp-801/README.md). Не входить: Elasticsearch |
| TP-802 | Internal notifications, unread state and idempotent reminders; SPEC §15; [frozen contract](../architecture/tp-802-notifications-contract.md) | `GET /notifications?status=&cursor=`, `POST /notifications/{id}/read`, `POST /notifications/read-all`; recipient-only selector, stable `(recipient, event_key)`, relative role-safe links, Celery retry/concurrency idempotency | `/notifications`: all/unread, numeric badge, today/yesterday/date groups, loading/error/retry/empty, cursor, read/read-all і safe deep links | `done` 2026-07-22: arrival/cancel, payment-ready, password-reset, upcoming appointment і overdue work-item events; 21 focused, 340 backend, 180 frontend і 37 axe; migration/runtime/worker/beat та authenticated responsive browser gates green; [evidence](../evidence/tp-802/README.md). Не входить: SMS/email/messengers |
| TP-803 | Admin audit list/detail «Було → Стало»; SPEC §14; [frozen contract](../architecture/tp-803-audit-ui-contract.md); AC-20 | TP-207 search/actor/section/date/cursor endpoints; inverted range `422`; complete action registry; redacted snapshots and stable object references | `/audit`: admin-only loading/empty/error/retry/filter/cursor/reload-stable detail; mobile fullscreen/focus/body lock; other roles hidden + 403 | `done` 2026-07-22: 44 focused backend, 342 canonical backend, 187 frontend і 38 axe; migration-free/runtime та authenticated responsive browser gates green; [evidence](../evidence/tp-803/README.md). Не входить: edit/delete/export |
| TP-804 | Role overview projections and admin analytics; SPEC §5, §13; [frozen contract](../architecture/tp-804-overview-analytics-contract.md) | `GET /overview?date=`, admin-only `GET /analytics?from=&to=&specialist_id=&service_id=`; role-scoped projections, inclusive `Europe/Kyiv` range ≤366 днів, visits/ledger-derived totals, refunds subtract revenue, immutable service lines | `/` без demo numbers; `/analytics` month/quarter/year/custom + specialist/service filters, loading/empty/error/retry, adaptive KPI/trend/outcomes/utilization/ranking; podologist/reception/admin overview variants | `done` 2026-07-22: 3 focused backend, 4 frontend, canonical 345 backend/192 frontend/39 axe; OpenAPI/types, control reconciliation, migration-free runtime та authenticated responsive browser gates green. [Evidence](../evidence/tp-804/README.md). Не входить: unapproved async export |

### Етап 9 — production gate

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-901 | Cross-feature responsive, accessibility and resilience sweep; SPEC §18–19; AC-23; [frozen gate](../architecture/tp-901-cross-feature-quality-gate.md) | API unchanged; conflict/retry semantics frozen | Keyboard/focus/labels/contrast/touch; all critical loading/empty/error/offline/unsaved states on three viewports | `done` 2026-07-22: 13 routes × 3 viewport, native Edge axe/keyboard/touch/overflow gate, 18 visual baselines, shell retry і partial-widget regressions; canonical 345 backend/194 frontend/39 axe green. [Evidence](../evidence/tp-901/README.md). Не входить: new features або TP-902 session/security hardening |
| TP-902 | Security/privacy hardening; SPEC §2.4, §3, §14, §20; [frozen gate](../architecture/tp-902-security-privacy-hardening.md) | Redis email/IP login rate limit; 30m idle + 12h absolute expiry; secure cookie/HTTPS/HSTS/CSP/no-store; canonical upload decode; selector/serializer IDOR defense; audit/log redaction | Expired protected request unmount-ить shell і показує safe login notice; invalid login generic; 403/404/network states не розкривають object/account | `done` 2026-07-22: 352 backend, 198 frontend, 40 axe, OpenAPI/migration/runtime/deploy/browser gates; npm/pip audits мають 0 known critical/high findings. [Evidence](../evidence/tp-902/README.md). Не входить: external SSO/WAF/SIEM |
| TP-903 | Backup/restore, deployment and rollback rehearsal; [frozen contract](../architecture/tp-903-backup-deployment-contract.md) | Provider-neutral encrypted PostgreSQL + private-object recovery point; 30 daily/12 monthly retention; file secrets; backward-compatible migration order; immutable deployment state | Admin has no direct backup UI requirement | `done` 2026-07-22: final restore `53` migrations/`10` objects, `0` missing/pending/invalid, immutable deploy and image-only rollback `200/200/401`, ops image Scout `0C/0H/0M/0L`; canonical 357 backend/198 frontend/40 axe. [Evidence](../evidence/tp-903/README.md). Не входить: provider-specific product feature |
| TP-904 | Full role UAT and 23/23 acceptance release gate; SPEC §21; [frozen gate](../architecture/tp-904-release-acceptance-gate.md) | Frozen OpenAPI, migration from empty/populated DB, production health/readiness, machine-readable AC-01—AC-23 manifest | Podologist/reception/admin route journeys на 1440×900, 1024×768 і 390×844; read-only live UAT, mutation semantics у automated gates | `done` 2026-07-23: 23/23 verified; 3 roles × 3 viewport, 75 route checks, 11 forbidden redirects, 0 serious/critical axe і clean console; canonical 364 backend/198 frontend/40 axe, fresh/populated DB, dependency/image scans та production rehearsal green. [Evidence](../evidence/tp-904/README.md). Не входить: post-MVP backlog |

### Етап 10 — post-MVP

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-1001 | Окремий supplier directory та прив’язка надходжень; GAP-11; [frozen contract](../architecture/tp-1001-supplier-directory-contract.md) | Admin-only `GET/POST /inventory/suppliers`, `GET/PATCH /inventory/suppliers/{id}`; case-insensitive unique name, optimistic version, no delete; optional active `supplier_id` у receipt line, immutable lot name snapshot і legacy-name migration | Третій розділ `/inventory`: loading/empty/search/filter/error/retry, create/edit/deactivate/reactivate/unsaved; active supplier picker у receipt | `done` 2026-07-23: 23 focused supplier backend, 372 canonical backend, 200 frontend і 40 axe; OpenAPI/types, legacy migration, runtime та authenticated desktop/tablet/mobile browser gates green. [Evidence](../evidence/tp-1001/README.md). Не входить: purchase orders, payables, contracts, files, import/export |
| TP-1002 | Filtered CSV export журналу рухів; GAP-18; [frozen contract](../architecture/tp-1002-inventory-movement-export-contract.md) | Admin-only `GET /inventory/movements/export`; filter parity без cursor, stable 15-column UTF-8 BOM CSV, local timestamps, 5000-row/366-day bounds, formula-injection protection, no-store | `Експортувати CSV` у журналі: applied filters only, loading/disabled, server filename, error/retry, 44px responsive target | `done` 2026-07-23: 8 focused export, 380 canonical backend, 202 frontend, 40 axe, live HTTP bytes/headers і desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1002/README.md). Не входить: cash/finance, analytics, audit, patient/visit export; XLSX/PDF/background jobs |
| TP-1003 | Exact cash-shift detail CSV; prototype `#exportCashShift`; [frozen contract](../architecture/tp-1003-cash-shift-detail-export-contract.md) | `GET /cash-shifts/{id}/export`; same admin/owner object scope, summary-first stable 23-column UTF-8 BOM CSV, 5000-entry bound, no patient/service joins, formula protection, no-store | `Експортувати CSV` лише в exact detail: pending/disabled, server filename, success/error/retry без закриття dialog, 44px target | `done` 2026-07-23: 5 focused cash-shift export, 385 canonical backend, 204 frontend, 40 axe, live HTTP bytes/headers і desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1003/README.md). Не входить: period/multi-shift/finance operations, analytics/audit, receipt/PDF/XLSX/jobs |
| TP-1004 | Filtered CSV report історії касових змін; prototype `.history-export`; GAP-18; [frozen contract](../architecture/tp-1004-cash-shift-history-export-contract.md) | `GET /cash-shifts/export`; same list filters без cursor, admin/all vs reception/own, summary-first stable 28-column UTF-8 BOM CSV, 5000 shifts/366 days, no ledger/patient/service rows, no-store | `Експортувати CSV` лише в history header: applied filters, pending/disabled, server filename, success/error/retry, rows/cards/detail лишаються видимими, 44px target | `done` 2026-07-23: 5 focused backend, 143 focused frontend, 390 canonical backend, 206 canonical frontend і 40 axe; live HTTP bytes/headers та desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1004/README.md). Не входить: ledger rows, finance operations, analytics/audit, PDF/XLSX/jobs |
| TP-1005 | Aggregate analytics CSV; prototype `#exportAnalytics`; [frozen contract](../architecture/tp-1005-analytics-export-contract.md) | Admin-only `GET /analytics/export`; exact existing filters/read model, summary-first stable 34-column UTF-8 BOM multi-section CSV, 5000 rows/366 days, no raw patient/clinical/operation identifiers, no-store | `Експортувати CSV` у analytics heading: current loaded projection only, pending/disabled, server filename, success/error/retry, KPI/charts/tables лишаються видимими, 44px target | `done` 2026-07-23: 8 focused backend, 140 focused frontend, 395 canonical backend, 208 canonical frontend і 40 axe; live HTTP bytes/headers та desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1005/README.md). Не входить: raw rows, finance operations, audit, PDF/XLSX/jobs |
| TP-1006 | Filtered CSV журналу фінансових операцій; prototype `data-finance-admin`; GAP-18; [frozen contract](../architecture/tp-1006-finance-operation-export-contract.md) | Admin-only `GET /finance/operations/export`; exact six main-list filters без cursor, summary-first stable 41-column UTF-8 BOM CSV, 5000 rows/366 days, no phone/internal UUID/raw ledger/audit/clinical fields, no-store | `Експортувати CSV` лише admin у operations header: applied query only, pending/disabled, server filename, success/error/retry, shift/filters/rows лишаються видимими, 44px target | `done` 2026-07-23: 6 focused backend, 28 focused frontend, 401 canonical backend, 211 canonical frontend і 40 axe; live HTTP bytes/headers та desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1006/README.md). Не входить: reception export, audit, receipt print/send, PDF/XLSX/jobs |
| TP-1007 | Filtered CSV журналу дій; prototype `#exportAuditLog`; GAP-18; [frozen contract](../architecture/tp-1007-audit-export-contract.md) | Admin-only `GET /audit-events/export`; exact five list filters без cursor, summary-first stable 28-column UTF-8 BOM CSV, 5000 rows/366 days, no before/after/note/correlation/actor-email/object-ID/clinical/security payload, no-store | `Експортувати CSV` у `/audit` heading: applied query only, pending/disabled, server filename, success/error/retry, filters/list/detail лишаються видимими, 44px target | `done` 2026-07-23: 6 focused backend, 8 AuditPage scenarios, 407 canonical backend, 213 frontend і 40 axe; live HTTP bytes/headers та desktop/tablet/mobile gates green. [Evidence](../evidence/tp-1007/README.md). Не входить: non-admin export, full snapshots, legal archive, retention, PDF/XLSX/jobs |

### Етап 11 — заявки та інтеграції

| ID | Вертикальний результат і джерела | API та інваріанти | UI, доступ і стани | Залежності, доказ і «не входить» |
|---|---|---|---|---|
| TP-1008 | Role-scoped реєстр заявок; [frozen contract](../architecture/tp-1008-1011-booking-requests-telegram-contract.md) | `GET /booking-requests`, `GET /booking-requests/{id}`, `POST /booking-requests/{id}/process`; immutable contact payload з optional client name/phone/service/comment, NEW→PROCESSED, row lock/version, repeated process idempotent, same-transaction audit | `/booking-requests` для admin/reception: counts, status/source/search/cursor, desktop table/mobile cards, reload-stable detail, explicit empty-field fallbacks, process/conflict/already states | `done` 2026-07-28: 11 focused backend, 8 focused frontend, 426 canonical backend, 223 frontend і 42 axe; role/responsive/optional-field browser gates green. [Evidence](../evidence/tp-1008/README.md). Не входить: external create, token, Telegram, edit/delete, patient/appointment conversion |
| TP-1009 | Server-to-server прийом заявок і admin token lifecycle; [API guide](../integrations/booking-requests-api.md) | `GET /booking-request-integration`, `POST /booking-request-integration/token/rotate`, `POST /integrations/booking-requests`; digest-only Bearer, one-time plaintext, strict payload, rate limit, Idempotency-Key/payload hash | `/settings` integration tab: generate/rotate warning/copy-once; external guide/OpenAPI placeholder-only | `done` 2026-07-28: 8 focused backend, 2 focused frontend, 434 canonical backend, 225 frontend і 42 axe; live create/replay/mismatch та responsive browser gates green. [Evidence](../evidence/tp-1009/README.md). Не входить: browser secret, multiple tokens, Telegram |
| TP-1010 | Private Telegram authorization і durable fan-out | `GET /telegram/subscription`, `POST /telegram/link-intents`, `DELETE /telegram/subscription`, verified Telegram webhook; one-time link, private-chat/role checks, update dedupe, delivery outbox/retry | Personal profile connect/disconnect; нова заявка надходить усім enabled eligible admin/reception chats | `planned`; TP-1009. Fake Bot API/link/webhook/fan-out/retry gates. Не входить: callback/process sync, groups, real production token |
| TP-1011 | Inline process і синхронізація всіх Telegram copies | Authorized `br:p:<uuid>` callback викликає той самий domain service; answerCallbackQuery, stale-version delivery edit, 429/backoff/permanent-failure isolation | `✅ Оброблено` в боті; після CRM або bot action доступні messages best-effort змінюють status, прибирають action і зберігають CRM link | `planned`; TP-1010 + rotated production bot token. Race/replay/cross-chat/production gates. Не входить: гарантія edit видалених/blocked messages, client chatbot |

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
| AC-14 | TP-701—703 | TP-904 |
| AC-15 | TP-703 | TP-904 |
| AC-16 | TP-701, TP-704 | TP-904 |
| AC-17 | TP-704 | TP-904 |
| AC-18 | TP-502, TP-604 | TP-904 |
| AC-19 | TP-502—503 | TP-904 |
| AC-20 | TP-207, TP-803 | TP-904 |
| AC-21 | TP-202—203 | TP-902 |
| AC-22 | TP-801—802 | TP-902 |
| AC-23 | TP-103, TP-404, TP-901 | TP-904 |

## 6. Порядок найближчого запуску

ERD та ADR-001—ADR-006 погоджені 2026-07-20; TP-101—TP-103, TP-201—TP-207, TP-301—TP-303, TP-401—TP-404, TP-501—TP-503, TP-601—TP-605, TP-701—TP-704, TP-801—TP-804, TP-901—TP-904 і post-MVP TP-1001—TP-1009 завершено. TP-904 закрив MVP із `23/23 verified`; TP-1001 закрив GAP-11 supplier directory, TP-1002—TP-1007 — safe CSV slices та GAP-18, TP-1008 — role-scoped CRM register заявок, TP-1009 — Bearer token lifecycle та external create API. Наступний packet — `TP-1010 planned`: private Telegram authorization і durable fan-out за [планом TP-1008—TP-1011](booking-requests-telegram-implementation-plan.md).
