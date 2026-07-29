# Поточний checkpoint розробки

Дата: 2026-07-30

## Зафіксований стан

- TP-201—TP-207, TP-301—TP-303, TP-401—TP-404, TP-501—TP-503, TP-601—TP-605, TP-701—TP-704, TP-801—TP-804 і TP-901—TP-903 завершені. TP-903 додав encrypted off-host recovery points, isolated restore verification, immutable production-like deployment і image-only rollback; [evidence](../evidence/tp-903/README.md).
- Реалізовані session auth/RBAC, password lifecycle, команда працівників, append-only audit, профіль клініки, приватний логотип, кабінети, каталог послуг, вісім системних статусів, clinic-wide графік із перервами та admin-only каталог матеріалів/партій.
- OpenAPI snapshot і TypeScript API schema оновлені разом із backend/frontend реалізацією.
- TP-301 реалізує normalized/indexed non-unique phone, стабільний public patient number, cursor pagination, live search, role-scoped selector, duplicate warning, atomic patient-create audit і responsive create/list UI.
- TP-302 реалізує one-to-one medical profile, role-specific `GET/PATCH /patients/{id}` projections, selector-level foreign-patient IDOR, atomic row-locked patient edit audit і responsive patient-card shell. Reception payload не має medical/photo keys; TP-605 заповнив completed history, photo archive та recommendations реальними role-scoped проєкціями.
- TP-303 реалізує `GET/POST /work-items`, versioned `PATCH /work-items/{id}`, own/all role scope, safe patient link, active assignee та podologist/patient relationship validation, importance/due time й explicit complete/reopen. Create/update/complete/reopen атомарно пишуть audit; callback із картки пацієнта лише створює справу і не запускає дзвінок.
- TP-401 реалізує PostgreSQL appointment time ranges з partial exclusion constraints для спеціаліста й кабінету, role-scoped `GET /calendar`, `GET /appointments/availability` з clinic-wide робочими годинами/перервами та day/week UI з окремим внутрішнім horizontal scroll.
- TP-402 реалізує transactional `POST /appointments` із server-derived snapshots/NEW status, role-visible patient і active resource validation, podologist-to-self, complaint XOR, clinic-time/occupancy checks, concurrent `409 appointment_slot_conflict`, atomic audit та responsive CTA/slot/locked-patient/inline-create UI.
- TP-403 реалізує role-scoped `GET/PATCH /appointments/{id}`, окремі status/cancel actions, row lock + optimistic `version`, self-excluding reschedule occupancy, server-provided allowed transitions, terminal/visit guards, required cancellation reason, slot release й atomic before/after audit для update/reschedule/status/cancel.
- TP-404 формалізує exact-viewport day/week gate: named/focusable internal scroll, видимі scroll hints, 44px tablet/mobile targets, capped sticky grid, concurrent no-overlap/text-clipping assertions і detail focus-return без нового business API.
- TP-501 реалізує admin-only `Material`/`MaterialLot`, create/update/deactivate/reactivate без delete, atomic audit, optimistic version, незмінні unit після першої партії та lot identity, expiry/available/FEFO projections, search/filter/catalog/details UI і unsaved guard. Пряме редагування lots лишається забороненим; balance змінюють лише проведені операції TP-502. У межах MVP supplier був лише lot/receipt attribute; TP-1001 додав окремий post-MVP directory без зміни історичних snapshot.
- TP-502 реалізує idempotent multi-line receipt і locked manual write-off з детермінованим lock order, full pre-mutation validation, no-negative balance, append-only operations/movements, atomic audit та admin-only responsive forms. Existing-lot receipt потребує явного підтвердження і збігу immutable details.
- TP-503 реалізує immutable DRAFT stocktake snapshot, idempotent create/post, sorted row locks, stale-balance `409`, append-only `STOCKTAKE_ADJUSTMENT`, atomic audit, read-only posted state та cursor movement journal/search/date/kind/material/actor filters з operation detail. Responsive UI має preview, difference/valuation, confirm/post/retry/unsaved guards і read-only journal detail.
- TP-601 реалізує `POST /appointments/{id}/start-visit`, `GET /visits/{id}` і versioned `PUT /visits/{id}`: лише ARRIVED appointment, один visit на appointment, assigned podologist/admin scope, atomic ARRIVED→IN_PROGRESS transition та idempotent retry без duplicate audit. Examination draft має complaint XOR, objective examination, фіксований condition registry, notes, autosave/manual save, optimistic conflict і unsaved guard; жодних stock/finance/completion side effects.
- TP-602 розширює visit draft snapshot-рядками послуг і матеріалів: primary service seed, integer service quantities/totals/dedup, decimal material quantity, active-service search і visit-scoped FEFO picker лише з придатними партіями. Save атомарно замінює рядки під optimistic version, пише один audit і не змінює склад; insufficient/unusable/duplicate input відхиляється без часткового mutation.
- TP-603 реалізує visit-owned private `VisitPhoto` та короткоживучий upload intent: replay-safe multipart finalize канонізує JPEG/PNG/WebP без EXIF/GPS, перевіряє magic/decode, 10 МБ і 10 фото на kind, створює async preview після commit та повертає лише authenticated signed URLs до 5 хвилин. Reception не отримує visit/photo metadata, assigned podologist/admin проходять object scope; draft delete й add/delete audit атомарні, completed visit immutable, cleanup прибирає expired intents та orphan objects. Thumbnail відкривається у visit-wide popup slider з BEFORE/AFTER caption, counter, cyclic arrows, ←/→, `Esc`, focus trap і focus return.
- TP-604 реалізує `POST /visits/{id}/finish` із required `Idempotency-Key`, payload hash і збереженим replay result. Lock order appointment→visit→sorted lots, optimistic visit version, повна pre-mutation перевірка stock/photo/follow-up slot та одна transaction гарантують, що appointment/visit completion, `VISIT_USAGE` movements, server-derived receivable, recommendation, optional follow-up і audit або commit-яться разом, або повністю відкочуються. Крок 4 показує summary, суму, матеріали/фото, recommendation, payment handoff, optional follow-up availability, explicit confirmation, conflict refresh/retry і success state без проведення фактичної оплати.
- TP-605 реалізує role-safe `GET /patients/{id}/visits`, medical-only photo/recommendation archive, exact recommendation refresh та visit-scoped POST/PATCH. Reception JSON фізично не має clinical/photo/recommendation keys; podologist бачить лише власні completed visits, admin — дозволену повну проєкцію. Історія використовує stable service/cost snapshots і cursor, фото згруповані за visit у popup carousel з окремими «До / Після», thumbnails, counter, signed-URL retry, keyboard/focus lifecycle та mobile fullscreen. Рекомендації мають visit/date/author, optimistic version recovery, unsaved/navigation guard і same-transaction create/update audit.
- TP-701 реалізує reception/admin `POST /cash-shifts` без request body та `GET /cash-shifts/current` для власної зміни. Partial unique constraint і user-row lock дають одну OPEN-зміну на працівника та стабільний `409 cash_shift_already_open`; same-transaction audit failure повністю відкочує відкриття. Current projection серіалізує ledger entries і всі totals лише з append-only rows. PostgreSQL triggers, model/queryset guards і read-only admin блокують delete, identity mutation, reopen та редагування ledger. `/finance` має loading/error/retry/no-shift/zero-balance confirmation/current summary/semantic ledger states; TP-702 додає operation list і full-payment controls.
- TP-702 реалізує [finance contract](../architecture/tp-702-finance-contract.md): `GET /finance/operations` є paid+unpaid union з одним стабільним рядком на Receivable; `POST /payments` приймає тільки `visit_id`, `payment_method` і optional `comment`, а повну суму визначає сервер. Mutation потребує `Idempotency-Key`, own OPEN shift і same-transaction audit; idempotency та unique constraints дають один результат при concurrent submit. Zero-total receivable auto-settle-иться у `PAID` без Payment/ledger. Шість billing triggers, зокрема два взаємні deferred aggregate guards, захищають ledger і Receivable↔Payment consistency; close/reconciliation/history доповнює TP-704 нижче.
- TP-703 реалізує [refund/cash contract](../architecture/tp-703-refund-cash-contract.md): одне повне server-derived повернення успадковує original method і може бути проведене з історичної payment у власну current OPEN shift actor; cash refund/withdrawal повторно перевіряють physical cash під lock. `GET /finance/operations` additively отримує singular nullable refund на стабільному PAYMENT row та окремі tagged REFUND/DEPOSIT/WITHDRAWAL rows. Strict cash-movement schema не має patient/payment method, а DEPOSIT і WITHDRAWAL ділять один idempotency family. Immutable typed extensions, 13 billing triggers, idempotency/concurrency та atomic audit gates пройшли; status `done` 2026-07-22.
- TP-704 реалізує [cash shift close/history contract](../architecture/tp-704-cash-shift-close-history-contract.md): authoritative close preview з clinic-wide unpaid warning, revisioned exact-idempotent close під shift lock, ledger-derived reconciliation, immutable opener/closer/actor snapshots, own-only reception та all-shifts admin history, cursor/filter list і повний detail. `/finance` отримав close dialog, а `/finance/shifts` — history/table/cards/detail зі stale-preview refresh, exact network retry та already-closed recovery. DB guards блокують reopen/delete, неправильну formula/comment і insert ledger row до CLOSED shift.
- TP-801 реалізує [frozen global-search contract](../architecture/tp-801-global-search-contract.md): `GET /api/v1/search?q=&types=` застосовує role/object scope до handlers, match, ranking, limit і serialization; шукає patients, appointments, payments і materials з exact/prefix/substring ranking через `pg_trgm` та вісім targeted GIN indexes. Responsive overlay має grouped loading/empty/error/retry states, `Ctrl/Cmd+K`, keyboard/focus/body-lock lifecycle і canonical deep links; appointment/payment/material details відновлюються після reload і очищають query parameter при close.
- TP-802 реалізує [frozen notifications contract](../architecture/tp-802-notifications-contract.md): recipient-owned `Notification` з unique `(recipient, event_key)`, role-safe relative deep link і server `read_at`; list/all/unread/cursor, read, read-all та session unread count API. Immediate domain hooks працюють через `on_commit()`, а щохвилинний Celery beat створює upcoming appointment і overdue work-item reminders без duplicate retry/race. Responsive `/notifications` має numeric badge, ordered Today/Yesterday/date groups, loading/error/retry/empty, cursor і синхронний read state.
- TP-803 реалізує [frozen audit UI contract](../architecture/tp-803-audit-ui-contract.md): admin-only `/audit`, search/employee/section/date filters, cursor list і `?event=<uuid>` detail з redacted «Було → Стало», historical actor/object snapshots, correlation context та allowlisted links. Registry completeness охоплює всі `AuditAction`; edit/delete/export UI відсутній.
- TP-804 реалізує [frozen overview/analytics contract](../architecture/tp-804-overview-analytics-contract.md): role-scoped `GET /overview?date=`, admin-only `GET /analytics?from=&to=&specialist_id=&service_id=`, inclusive `Europe/Kyiv` range ≤366 днів, net ledger revenue, cohorts, immutable service ranking і clinic-schedule utilization. `/` не містить demo numbers, `/analytics` не містить непогодженого export.
- TP-901 реалізує [frozen cross-feature quality gate](../architecture/tp-901-cross-feature-quality-gate.md) без API/models/migrations: централізовані AA color tokens, keyboard-accessible analytics scroll regions, 44 px primary touch targets, skip-link focus, shared modal focus/body-lock lifecycle, shell offline retry і partial-widget resilience.
- TP-902 реалізує [frozen security/privacy gate](../architecture/tp-902-security-privacy-hardening.md): concurrency-safe Redis email/IP login counters, generic `429` + `Retry-After`, 30m idle/12h absolute server session, `401 session_expired`, Secure/HTTPS/HSTS/CSP/no-store boundary, non-development secret guard, full Pillow decode/re-encode для logo, audit/JSON-log redaction і frontend protected-DOM unmount після будь-якого protected `401`.
- TP-903 реалізує [frozen backup/deployment contract](../architecture/tp-903-backup-deployment-contract.md): encrypted PostgreSQL/MinIO recovery point з checksums/manifest, 30 daily/12 monthly retention, окремі file credentials, isolated tmpfs restore verifier, source-mount-free immutable deployment та image-only rollback без автоматичних reverse migrations.
- Browser/operations evidence для TP-203—TP-206, TP-301—TP-303, TP-401—TP-404, TP-501—TP-503, TP-601—TP-605, TP-701—TP-704, TP-801—TP-804 і TP-901—TP-903 збережені в `docs/evidence/`. TP-903 [evidence](../evidence/tp-903/README.md) містить machine-readable recovery/deploy/rollback/security gate.
- Кореневий `AGENTS.md` вимагає окремо діагностувати й відновлювати несправні локальні компоненти замість повторення того самого невдалого виклику.

## Локальне середовище

- Docker Compose stack відновлений і readiness endpoint повертає `200`.
- Завислий orphan-контейнер `podoria-crm-backend-stuck` видалений; робочий контейнер `podoria-crm-backend-1` healthy.
- Вбудований браузер перевірений на `http://127.0.0.1:8088/settings`.
- Локальні credentials тестового адміністратора зберігаються лише в проігнорованому `.env.local`; `README.md` містить команду відтворення без відкритого пароля, а `.env.example` — безпечні placeholders.
- TP-206 gate: 93 backend tests і 33 frontend tests, Ruff, mypy, Django checks/migrations, lint, typecheck, contracts/OpenAPI і production build пройшли. Одноразовий `frontend-test` process segfault після lint окремо діагностовано; свіжий мінімальний typecheck і повний container check стабільно пройшли.
- Під час пізнішого повтору combined gate Docker Desktop не отримав exit event від точного `frontend-test` контейнера й не зміг його зупинити. Docker Desktop точково перезапущено; завислий контейнер зник, Compose stack знову healthy, readiness і `/settings` повертають `200`, а новий одноразовий frontend-контейнер виконав typecheck і був автоматично видалений. Stale test containers не лишилися.
- На початку TP-301 Docker API знову перестав відповідати під час першого backend check. Перевірено host processes і Docker logs, завислі клієнти зупинено, Docker Desktop перезапущено. Старий stateless backend-контейнер мав точний OCI blocker `container's cgroup is not empty`; його mounts перевірено, відтворено лише backend-контейнер без БД/volume змін. Після code-level admin typing fix stack, migrations і readiness відновлені.
- TP-301 gate: 110 backend tests і 40 frontend tests, Ruff/format, mypy, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, typecheck, 8 axe routes і production build пройшли. Host `npm run check` очікувано не має container-only `frontend/openapi/schema.json`; canonical fresh `frontend-test` gate із copied backend snapshot пройшов повністю.
- TP-302 gate: 120 backend tests і 46 frontend tests, Ruff/format, mypy для 74 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 9 axe routes, canonical fresh `frontend-test` і production web build пройшли.
- TP-303 gate: 129 backend tests і 53 frontend tests, Ruff/format, mypy для 86 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 10 axe routes, canonical `frontend-tools` check і production web build пройшли. Host `npm run check` очікувано не бачить container-only `frontend/openapi/schema.json`; призначений Compose tools gate підтвердив контракт без дублювання snapshot.
- TP-401 gate: 134 backend tests і 58 frontend tests, Ruff/format для 121 Python files, mypy для 96 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 11 axe routes, canonical `scripts/run-tests.ps1` і production web build пройшли. Stack healthy, readiness і `/calendar` повертають `200`.
- TP-402 gate: 143 backend tests і 64 frontend tests, Ruff/format для 123 Python files, mypy для 97 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 12 axe routes, canonical `scripts/run-tests.ps1` і production web build пройшли. Web/backend/postgres healthy, proxy `/` повертає `200`.
- TP-403 gate: 153 backend tests і 68 frontend tests, Ruff/format для 125 Python files, mypy для 98 source files, Django checks/migrations, OpenAPI snapshot, required-version contract, generated client, lint, strict typecheck, 13 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Web/backend/postgres healthy, readiness повертає `200`.
- TP-404 gate: 153 backend tests і 70 frontend tests, Ruff/format для 125 Python files, mypy для 98 source files, Django checks/migrations, OpenAPI snapshot/generated client, contracts, lint, strict typecheck, 13 axe scenarios, native Edge layout/focus harness, canonical `scripts/run-tests.ps1` і production web build пройшли.
- TP-501 gate: 161 backend tests і 75 frontend tests, Ruff/format для 137 Python files, mypy для 108 source files, Django checks/migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 14 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Під час gate OpenAPI snapshot виявився YAML у `.json`; його точково перегенеровано з `--format openapi-json`, два contract tests повторно пройшли. Compose має production-сервіс `web`, а source frontend checks штатно виконуються host Node або `frontend-test`/`frontend-tools`.
- TP-502 gate: 170 backend tests і 81 frontend tests, Ruff/format для 139 Python files, mypy для 109 source files, Django checks/clean migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 16 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Browser gate виявив і виправив overflow existing-lot confirmation у receipt grid; повторна desktop/tablet/mobile перевірка пройшла без console errors.
- TP-503 gate: 183 backend tests і 86 frontend tests, Ruff/format для 141 Python files, mypy для 110 source files, Django checks/clean migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 18 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Перші дві web build спроби залишили orphan Compose/Buildx clients і завислий BuildKit exec lease; точні process chains та build history перевірено, orphan clients зупинено, Docker Desktop контрольовано перезапущено, stack/readiness відновлено, а чиста повторна build завершилася за 22.5 с.
- TP-601 gate: 192 backend tests і 92 frontend tests, Ruff/format для 153 Python files, mypy для 120 source files, Django checks/clean migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 20 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Concurrent start повертає рівно один `201` і один idempotent `200`, створюючи один visit та один start audit; fault-injected audit failure повністю відкочує start/draft mutations.
- TP-602 gate: 201 backend tests і 98 frontend tests, Ruff/format для 155 Python files, mypy для 121 source files, Django checks/migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 21 axe scenario, canonical `scripts/run-tests.ps1` і production Vite build пройшли. Під час fixture cleanup виявлено й виправлено deferred-field recursion у `MaterialLot.from_db`; окремий регресійний тест підтверджує безпечне deferred load/delete та незмінність lot identity.
- TP-603 gate: 208 backend tests і 103 frontend tests, Ruff/format для 160 Python files, mypy для 125 source files, Django checks/clean migrations, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 22 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Перший повний frontend gate виявив container-specific `Request.formData()` assertion; перевірку multipart замінено на portable body assertion, фокусний контейнерний тест і весь gate повторно пройшли. Після recreation backend/web старий proxy утримував stale upstream IP та повертав 502; logs підтвердили точні IP, лише proxy відтворено, readiness і UI повернули 200.
- TP-604 gate: 218 backend tests і 106 frontend tests, Ruff/format для 171 Python files, mypy, Django checks/migrations from scratch, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, 23 axe scenarios, canonical `scripts/run-tests.ps1` і production web build пройшли. Fault injection і concurrent double-finish/finish-vs-writeoff/finish-vs-slot-create тести підтверджують один результат без partial rows або negative stock. Після recreation backend/web proxy знову мав stale upstream IP; logs показали `.4` проти актуальної `.5`, точковий restart лише proxy відновив `/health/ready` до `200`.
- TP-605 gate: 226 backend tests і 117 frontend tests, Ruff/format для 177 Python files, mypy для 140 source files, Django checks і clean migrations from scratch, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, production build та 28 axe scenarios пройшли у canonical `scripts/run-tests.ps1`. Role/IDOR, cursor, signed URL, optimistic recommendation conflict, audit rollback і patient-switch privacy regressions покриті. Після production recreation nginx кешував старі upstream IP; точковий restart лише proxy відновив readiness/UI до `200` без змін БД або volumes.
- TP-701 gate: 248 backend tests і 127 frontend tests, Ruff/format для 185 Python files, mypy для 145 source files, Django checks і clean migrations from scratch, OpenAPI JSON snapshot/generated client, contracts, lint, strict typecheck, production build та 30 axe scenarios пройшли у canonical `scripts/run-tests.ps1`. Focused billing gate мав 22 backend tests, FinancePage — 6 component tests і 2 axe scenarios. Forward→reverse→forward migration smoke підтвердив обидва DB triggers. Після build timeout діагностовано orphan Compose/Buildx chain і broken built-in BuildKit session; зупинено лише точні orphan PID/refs, створено isolated builder, recreated backend/worker/beat/web і перезапущено лише proxy зі stale upstream. Readiness і `/finance` повертають `200`, unauthenticated current endpoint — `401`, усі runtime-компоненти healthy/ready.
- TP-702 gate: canonical `scripts/run-tests.ps1` пройшов 266 backend tests, 137 frontend tests і 32 axe scenarios; focused billing gate — 50 tests, `FinancePage` — 14 tests. OpenAPI snapshot/generated client/contracts, static checks і production build чисті. Dev migration smoke пройшов rollback→reapply; перевірено шість billing triggers, серед них два взаємні deferred aggregate guards. Runtime `/`, `/finance` і `/health/ready` повертає `200`. Desktop/tablet/mobile automated browser gate перевірив unpaid detail і full-payment dialog без submit: amount inputs `0`, methods `3`, body scroll lock, focus return, horizontal overflow і console errors відсутні. Після окремої валідної оплати з live `localhost` UI read-only перевірено paid/card projection і immutable detail; zero-settled state підтверджено API/component tests.
- TP-703 gate: canonical `scripts/run-tests.ps1` пройшов 284 backend tests, 151 frontend tests і 35 axe scenarios; focused billing — 57 tests, TP-703 API — 18, `FinancePage` — 25. OpenAPI snapshot/generated client/contracts, static checks і production build чисті. Dev migration smoke пройшов forward→reverse→forward; активні 13 billing triggers. Runtime `/`, `/finance` і `/health/ready` повертає `200`. Read-only browser gate на desktop/tablet/mobile перевірив refund/cash dialogs без submit, internal table scroll, fullscreen/body lock і нуль warning/error; dev DB лишився з 1 user-owned payment, 0 refunds і 0 cash adjustments.
- TP-704 automated gate: canonical `scripts/run-tests.ps1` пройшов 298/298 backend tests, 164/164 frontend tests і 35/35 axe scenarios; focused billing — 71 tests, TP-704 API/migration — 14. OpenAPI snapshot/generated TypeScript schema, lint, strict typecheck і production build чисті. Dev migration `0004 → 0005 → 0004 → 0005` пройшла, фінальний `0005` applied; збережено OPEN shift `CSH-089CE5E936FC`, CARD payment `TXN-337279B7D390` на `390050`, counts `1/0/0/1`, opener/actor snapshots backfilled. Runtime `/`, `/finance`, `/finance/shifts` і `/health/ready` повертає `200`; authenticated read-only browser gate пройшов без POST.
- TP-801 gate: focused search `29/29`; canonical `327/327` backend, `174/174` frontend і `36/36` axe; Ruff/format `210` files, mypy `163` source files, schema/generated types/contracts/lint/typecheck/build green. Migration apply→reverse→reapply відновила `pg_trgm` та вісім indexes; dev snapshot не змінив OPEN `CSH-089CE5E936FC`, CARD `TXN-337279B7D390` на `390050`, counts payment/refund/cash-adjustment/ledger `1/0/0/1` і patients/appointments/materials `4/3/1`. Runtime business routes/readiness повернули `200`, unauthenticated search — `401`.
- TP-802 gate: focused notifications/session `21/21`; canonical `340/340` backend, `180/180` frontend і `37/37` axe; Ruff/format, mypy, Django/OpenAPI/generated types/contracts/lint/strict typecheck/build green. `notifications.0001_initial` пройшла forward/reverse/data-preservation/reapply, фінально applied без pending plan. Backend/web/proxy healthy, worker/beat running; щохвилинний reminder task виконувався успішно, runtime `/notifications` і readiness повернули `200`, unauthenticated API — `401`.
- TP-803 gate: focused audit/access/session/notifications `44/44` backend; canonical `342/342` backend, `187/187` frontend і `38/38` axe; Ruff/format, mypy, Django/OpenAPI/generated types/contracts/lint/strict typecheck/build green. Packet migration-free: no model changes і no pending plan. Backend/web/proxy healthy, `/audit` і readiness повернули `200`, unauthenticated audit API — `401`.
- TP-804 gate: focused analytics `3/3` backend і `4/4` frontend; canonical `345/345` backend, `192/192` frontend і `39/39` axe; Ruff, mypy для 180 source files, Django/OpenAPI/generated types/contracts/lint/strict typecheck/production build green. Packet migration-free: no model changes і no pending plan. Необмежений Vitest forks pool один раз аварійно завершив Node 24/V8 worker; ресурси й focused test перевірено, full suite стабільно відтворено з `maxWorkers: 2`, ліміт зафіксовано, штатний Docker build повторно пройшов. Backend/web/proxy healthy, `/`, `/analytics` і readiness повернули `200`.
- TP-901 gate: canonical `345/345` backend, `194/194` frontend і `39/39` component axe; Ruff/format, mypy для 180 source files, Django/OpenAPI/generated types/contracts/lint/strict typecheck/production build green. Native Edge: 13 routes × 3 viewport, `0` axe violations, `0` browser warnings/errors, `0` page overflow/undersized primary targets; keyboard/mobile journeys і 18 baselines green. Packet migration-free і read-only.
- TP-902 gate: canonical `352/352` backend, `198/198` frontend і `40/40` component axe; Ruff/format для 236 files, mypy для 182 source files, Django/OpenAPI/generated types/contracts/lint/strict typecheck/production build green. Packet migration-free; npm production audit має `0 vulnerabilities`, pip-audit — `No known vulnerabilities found`. Deploy check має `0` errors/critical warnings і один accepted low advisory W021 щодо HSTS preload, відкладений до TP-903 domain/rollback rehearsal.
- TP-903 gate: canonical `357/357` backend, `198/198` frontend і `40/40` component axe; Ruff/format для 243 files, mypy для 187 source files, Django/fresh migrations/OpenAPI/generated types/contracts/lint/strict typecheck/production build green. Recovery point `20260722T214238Z` відтворив `53` migrations і `10` objects за `8.3s`, verifier — `0` missing/pending/invalid. Candidate deploy та image-only rollback дали `200/200/401`; ops image Docker Scout — `0C/0H/0M/0L` для 81 package.
- На старті TP-901 in-app browser мав stale tab handle; порожній session scope підтверджено, нову вкладку створено й auth-route sweep успішно відновив компонент. Після CSS fixes runtime віддавав старий asset; compose config показав, що service називається `web`, його production image точково перебудовано, container став healthy і HTTP підтвердив нові tokens. Два перші canonical frontend runs виявили неповні overview mocks у notification/audit role-fallback tests; route-aware fixtures додано, targeted і full suites повторено, фінальний canonical gate пройшов. Під час останнього web image build інтегрований BuildKit executor двічі давав ESLint `SIGSEGV`, хоча RAM/disk були вільні й той самий lint у звичайному frontend-test container проходив; build через наявний isolated docker-container builder `podoria-tp701-recovery` пройшов 194/194 та завантажив фінальний image. Лише `web` recreated, stack healthy, `/`, `/analytics`, readiness — `200`, unauthenticated analytics API — `401`.
- Під час TP-802 frontend gate Docker Desktop утримував ESLint process у Linux kernel D-state. Перевірено process/container/kernel state та disk pressure; штатний restart Docker Desktop і точковий recreate stack відновили компонент. Мінімальний lint, повний frontend gate і фінальна production web image після відновлення стабільно пройшли.
- Під час фінального TP-801 snapshot Docker Desktop Windows bind-mount bridge transiently повернув `EIO` для `/app/locale`, а daemon не міг повторно змонтувати host path через `mkdir .../host/c: file exists`. Host source лишався читабельним; штатний restart Docker Desktop і точковий запуск попередніх контейнерів без видалення volumes/data відновили mount. Backend/web/proxy стали healthy, worker/beat — running, `manage.py check` повернув 0 issues, startup migration — `No migrations to apply`, readiness і `/` — `200`; повторний DB snapshot лишив усі TP-801/finance counts та суми незмінними.
- На старті TP-404 backend зупинився через Docker Desktop bind-mount `EIO` (`/app/locale`) і mount source error. Перевірено container states/logs/network/config; точковий backend recreate підтвердив file-sharing blocker, після штатного restart Docker Desktop bind mount, backend і readiness відновилися. Після recreate web proxy один раз тримав stale upstream IP; restart лише proxy повторно резолвив web, `/calendar` і `/health/ready` повернули `200`. Stateless worker/beat, які лишилися stopped після runtime restart, окремо відтворено; обидва підключилися до Redis і worker повідомив `ready`.
- На старті TP-403 Docker Desktop API pipe був відсутній. Перевірено context/processes, запущено точний Docker Desktop executable, після чого Docker server, усі healthy-контейнери й `/health/ready` відновилися. Пізніше одноразовий `frontend-tools` завершився segfault; Node/module/schema перевірено окремо, прямий генератор і повторний штатний `npm run generate:api` стабільно пройшли.
- Під час TP-302 Docker Desktop не отримав exit event старого backend-контейнера, а пізніше BuildKit лишив дві runtime-сесії з `0/0` steps. Обидва збої діагностовано окремо: зупинено лише підтверджені orphan CLI-процеси, видалено точні running build refs, Docker Desktop/BuildKit перезапущено, stack повернуто через `up -d --no-build`. Після відновлення одинарна runtime-збірка стабільно пройшла, `web` і backend healthy, readiness та `/patients` повертають `200`.

Browser adapter має точкове локальне виправлення у встановленому plugin cache для сумісності із захищеним `process` рантайму та вимкнення несправної ambient telemetry у browser runtime. Це виправлення лежить поза репозиторієм і може бути перезаписане під час оновлення плагіна; у такому разі потрібно окремо відновити компонент за правилом з `AGENTS.md`.

Під час TP-206 вбудований browser коректно виконав login, DOM interactions і responsive bounding-box checks. Його PNG compositor після повторних viewport override повертав stale/cropped tiles навіть після reload/new tab/full-page capture; фінальні screenshots тому відтворено `frontend/scripts/tp206-browser-check.mjs` у локальному Edge. Невалідний проміжний screenshot видалено. TP-301 повторно перевірено вбудованим browser без compositor blocker: create, live search, empty, duplicate/non-blocking create, unsaved guard і точні 1440×900, 768×1024, 390×844 layouts. TP-302 перевірено тим самим browser adapter: directory→card, medical edit із CSRF, server success, overview/history shells, responsive no-overflow і unsaved close guard. TP-303 перевірено без mutation тестових даних: work-items list/create і patient callback dialog на трьох viewport. TP-401 перевірено з двома одночасними appointments: day/week view, specialist filter і внутрішній horizontal scroll не створюють page overflow; viewport скинуто, вкладку закрито. На початку TP-402 browser мав stale tab handle з попередньої сесії; список вкладок підтвердив порожній session scope, створено нову вкладку й мінімальна навігація успішно відновила компонент. Далі перевірено form availability, slot preset, inline patient modal, unsaved guard і три viewport без console errors. TP-404 in-app browser підтвердив authenticated day/week DOM, exact overflow/touch metrics і dialog focus lifecycle; його compositor знову повернув stale tiles на tablet/mobile, тому чотири canonical PNG створено `frontend/scripts/tp404-browser-check.mjs`, а три невалідні JPEG видалено. TP-501 in-app browser підтвердив catalog/details/FEFO на desktop/tablet/mobile; під час gate виправлено 42px mobile close target і стиснений tablet toolbar. TP-502 in-app browser перевірив populated multi-line receipt і manual write-off без submit на desktop/tablet/mobile; виявлений overflow existing-lot пояснення виправлено, повторні метрики дали `0` horizontal overflow і `44px` controls. TP-503 browser перевірив populated stocktake із surplus/shortage/valuation на desktop і mobile та journal filters/read-only empty state на tablet; console чиста, mobile overflow `0`, stocktake не створювався. TP-601 browser відкрив authenticated visit examination route з seeded скаргою на desktop/tablet/mobile; 4-step navigation, summary, form controls і intentional internal step scroll лишилися читабельними, mobile page overflow дорівнював `0`, ключові кнопки мали `44px`, console errors/warnings були відсутні. Browser не зберігав чернетку: version лишилася `1`, draft audit count — `0`; exact fixtures видалені, viewport скинуто, вкладку закрито. На початку TP-602 попередній tab handle був stale; порожній session scope підтверджено й browser відновлено новою вкладкою та успішною auth-навігацією. Далі read-only gate перевірив seeded service/material lines, totals, пошук і FEFO picker на трьох viewport; page overflow `0`, mobile controls `44px`, console чиста. До очищення visit мав version `1`, draft audit та inventory operation/movement counts `0`; усі точні fixtures видалені, viewport скинуто, вкладку закрито. TP-603 browser відкрив authenticated step 3 із синтетичними private BEFORE/AFTER objects; signed previews мали natural size `480×360`, desktop cards стояли поруч, tablet/mobile — в одну колонку, overflow `0`, controls `44px`, console чиста. Full-page tablet compositor повторив stale-tile артефакт, тому canonical evidence збережено звичайними viewport captures. Browser не виконував upload/delete; version, intents і photo-write audit не змінилися. Exact visit/patient/appointment/service/room та чотири MinIO objects видалені, viewport скинуто, вкладку закрито. TP-604 browser відкрив authenticated finish step із synthetic service/material snapshot; рекомендація і confirmation були введені без submit. Кнопка finish стала active, default desktop і `390×844` мали page overflow `0` та чисту console; fixture видалено без inventory, receivable або follow-up rows, viewport скинуто, вкладку закрито. TP-605 browser відкрив authenticated archive із двома completed visits, шістьма private photos і трьома recommendations. На `1280×900` історія мала 2 cards без page overflow, signed slide був `1200×900`, dialog — `1180×856`; mouse arrows, ←/→, tabs і thumbnails змінювали counter/caption. Focus trap циклічно переходив між close та останньою thumbnail, `Esc` повертав фокус на origin, body lock відновлювався. На `390×844` dialog займав весь `375×844` client viewport, усі controls мали щонайменше `44px`, `scrollWidth=clientWidth=375`; на `834×1000` відобразились 3 recommendation cards без overflow. Dirty editor блокував `Esc` і browser Back, Continue повертав фокус у textbox, Discard не створив запис; harmless Forward лишав той самий закритий recommendations route. Console warnings/errors були відсутні. Exact fixture, пов’язаний work item і 12 MinIO objects видалено, viewport скинуто, вкладку закрито.

TP-704 browser gate відкрив authenticated `/finance` і `/finance/shifts`: close
dialog пройдено до enabled-стану та скасовано без POST, desktop history/detail
показали повний CARD ledger, а `768×1024` і `390×844` cards не мали page
overflow чи controls менших за 44 px. Console була чистою; viewport скинуто,
вкладку закрито, повторний DB snapshot лишив `CSH-089CE5E936FC` OPEN.

TP-801 browser gate перевірив desktop/tablet/mobile grouped search (3 groups,
4 options), `Ctrl/Cmd+K`, keyboard selection, `Escape`, focus return і body lock.
Exact patient route та appointment/payment/material details відкрили canonical links;
query-param dialogs пережили reload і очистилися під час close. Tablet не мав
overflow, mobile був fullscreen з controls ≥44 px, console чиста. Повторний DB
snapshot не виявив фінансових або domain mutations.

TP-802 browser gate перевірив `/notifications` на `1440×900`, `1024×768` і
`390×844`: Today перед Yesterday, badge `2 → 1 → 0`, item read, mark-all та
unread empty state. Page overflow відсутній, console warnings/errors — `0`.
Browser gate виявив порядок groups за insertion order; sort виправлено, додано
component regression test і повторно зібрано production web image. Два точні
evidence notifications лишилися прочитаними в локальній dev-історії.

TP-803 browser gate перевірив `/audit` на `1440×900`, `1024×768` і `390×844`:
admin navigation, section filter `47 → 6`, reload-stable detail, redacted «Було →
Стало», allowlisted patient link, focus return, mobile body lock та `Escape`.
Gate виявив і виправив обрізання desktop/tablet rows та 42 px mobile close target;
фінальні метрики без overflow, close 44×44, console warnings/errors — `0`.
Evidence використовує 47 наявних append-only events і не створює domain mutations.

TP-804 browser gate перевірив `/` і `/analytics` на `1440×900`, `1024×768` і
`390×844`: live admin projection, empty overview state, 6 analytics KPI, month→quarter
refetch `2026-07-01…2026-09-30`, adaptive grids/mobile shell та internal table scroll.
Page overflow і export CTA відсутні, console warnings/errors — `0`; gate був read-only.

TP-901 browser gate перевірив 13 critical routes на `1440×900`, `1024×768` і
`390×844`: 39 native axe scans, responsive shell, main landmark, page overflow,
44 px primary touch targets і clean console. Keyboard journey пройшов skip link,
`Ctrl+K`, `Escape`, focus return і desktop navigation; mobile More пройшов body
lock, secondary-route navigation, `Escape` і focus return. Виявлені contrast,
scroll-region, accessible-name, target-size і modal lifecycle дефекти виправлено;
18 representative screenshots та [machine-readable evidence](../evidence/tp-901/browser-gate.json)
збережено без domain mutations.

TP-902 browser gate server-side перевів authenticated admin session за idle deadline.
Після reload URL став `/login`, protected shell count — `0`, safe session notice — `1`,
horizontal overflow і console warnings/errors — `0`. Unknown-account login повернув лише
generic invalid-credentials alert. Evidence screenshot записано тільки після очищення й
перевірки порожніх email/password inputs; 127 expired local admin sessions та два exact
rate-limit counters прибрано, domain records не змінювались. Runtime root/API мають по
одному CSP header, API `no-store`/`DENY`/`nosniff`; [evidence](../evidence/tp-902/README.md).

TP-903 operations gate створив encrypted recovery point з PostgreSQL custom dump і повним
private MinIO snapshot, повторно відновив його в isolated tmpfs targets та перевірив усі
persisted object references. Production-like Compose без source bind mounts пройшов
immutable candidate deploy і image-only rollback без reverse migration; backup DB/MinIO
identities залишилися read-only. Фінальний ops image після заміни vulnerable packaged
MinIO/age clients на MinIO SDK та source-built `age` має `0C/0H/0M/0L` у Docker Scout;
[evidence](../evidence/tp-903/README.md).

## Поточний стан

TP-904 завершив MVP 2026-07-23 з `23/23 verified`; post-MVP TP-1001—TP-1007
також завершені. TP-1004 закрив погоджений prototype `.history-export` як
filtered summary-first CSV історії касових змін: stable 28 columns, UTF-8 BOM,
CRLF, local time, applied list filters без cursor, 5000 shifts/366 days,
no-store і spreadsheet-formula injection protection. Scope повторює list —
admin all visible, reception own only — без individual ledger rows та
patient/visit/service/typed Payment/Refund data. Finance-operations, analytics
і audit exports не додано. [Contract](../architecture/tp-1004-cash-shift-history-export-contract.md)
і [evidence](../evidence/tp-1004/README.md).

Фінальний TP-1004 gate: `5/5` нових focused backend, `10/10` разом із exact
shift export, `143/143` focused frontend, `390/390` canonical backend,
`206/206` canonical frontend і `40/40` axe. Ruff/format для 254 Python files,
mypy для 192 source files, Django checks, clean migrations, OpenAPI snapshot,
generated TypeScript schema, contracts, ESLint, strict typecheck і production
build — green.

Authenticated live HTTP probe з applied `search` і `status` підтвердив `200`,
CSV content type, BOM, CRLF, 28 columns, summary-first, no-store, server filename,
shift/row counts `1/2` і відсутність cursor. Browser gate на `1440×1000`,
`768×1024` і `390×844` підтвердив header CTA, success-state, збереження
table/cards, 0 horizontal overflow, `44px` target і clean console. Download
handle у in-app browser недоступний, тому bytes та headers окремо доведені
HTTP/integration gates.

Ручний mypy запуск без canonical `--no-sqlite-cache` впав на відсутньому в
runtime Python модулі `sqlite3`. Окрема recovery-підзадача перевірила traceback
і `backend/scripts/check.sh`, exact `cache.db` тимчасово перемістила та відновила;
мінімальний і повний canonical mypy пройшли. Під час browser setup advertised
fallback path для viewport docs був відсутній; authoritative file знайдено в
plugin `docs/`, інструкцію застосовано, capability set/reset пройшов.

Backend/web відтворені з `docker compose ... --wait`, readiness повернув `200`.
Volumes/domain data не змінювалися. Локальні credentials читалися лише з
Git-ignored `.env.local` і не потрапили у tracked output.

TP-1005 завершено за окремим
[frozen contract](../architecture/tp-1005-analytics-export-contract.md):
admin-only aggregate CSV поточної analytics projection, stable 34-column
summary/trend/outcome/specialist/service sections, 5000 rows/366 days і без raw
patient/visit/appointment/payment/refund/ledger identifiers. Focused gates:
`8/8` analytics backend і `140/140` frontend/accessibility; canonical gates:
`395/395` backend, `208/208` frontend і `40/40` axe. OpenAPI/types, lint,
strict typecheck і production build green. [Evidence](../evidence/tp-1005/README.md).

Authenticated live HTTP із чотирма applied analytics filters підтвердив `200`,
CSV content type, server filename, no-store, BOM, CRLF, 34 columns,
summary-first і row-count header/parser parity `37/37`. Browser gate на
`1440×1000`, `768×1024` і `390×844` підтвердив success state, content
preservation, відсутність horizontal overflow, 44px CTA та clean console.

Після backend/web recreate proxy мав stale backend upstream `172.19.0.6`, тоді
як healthy backend отримав `172.19.0.2`; окрема recovery-підзадача звірила
Compose/logs/IP, перезапустила лише proxy і повернула readiness/session `200`.
Завершальний browser viewport reset відновлено через authoritative `reset()`
після capability inspection. Volumes/domain data не змінювалися, credentials
лишилися тільки у Git-ignored `.env.local`.

TP-1006 завершено за окремим
[frozen contract](../architecture/tp-1006-finance-operation-export-contract.md):
admin-only CSV current finance-operation journal, exact six applied filters,
summary-first stable 41-column projection, 5000 rows/366 days та без phone,
internal UUID, raw ledger/audit/clinical fields. Audit export не входить.
Focused gates: `6/6` backend і `28/28` frontend; canonical gates: `401/401`
backend, `211/211` frontend і `40/40` axe. Ruff/format перевірили 256 Python
files, mypy — 193 source files; OpenAPI/types, lint, strict typecheck,
production build і production web image green.
[Evidence](../evidence/tp-1006/README.md).

Authenticated live HTTP з трьома applied filters підтвердив `200`, CSV content
type, server filename, no-store, BOM, CRLF, 41 columns, summary-first та
operation/row parity `1/2`. Browser gate на `1440×1000`, `768×1024` і
`390×844` підтвердив success/content preservation, `0` horizontal overflow,
44px CTA та clean console.

Паралельний frontend gate один раз завершив Vitest через Node `SIGSEGV`;
sequential запуск відокремив і дозволив виправити actual relative-URL defect.
Перший canonical wrapper був перерваний зовнішнім timeout, а дочірній
backend-test завис без stdout consumer. Container не реагував на stop/SIGKILL;
діагностика підтвердила zombie Docker daemon. Штатний restart Docker Desktop,
`docker compose up -d --wait` і readiness `200` відновили stack без видалення
volumes; повторний canonical gate повністю пройшов за `99s`. Browser viewport
скинуто, вкладку закрито, credentials лишилися тільки у Git-ignored
`.env.local`.

TP-1007 завершено за окремим
[frozen contract](../architecture/tp-1007-audit-export-contract.md):
admin-only CSV поточного audit journal, exact five applied filters,
summary-first stable 28-column projection, 5000 rows/366 days та без
before/after/changes, note, correlation ID, actor email/ID, object ID,
clinical/security payload. Focused gates: `6/6` backend і `8/8` AuditPage;
canonical gates: `407/407` backend, `213/213` frontend і `40/40` axe.
Ruff/format перевірили 258 Python files, mypy — 194 source files;
OpenAPI/types, lint, strict typecheck, production build та production web image
green. [Evidence](../evidence/tp-1007/README.md).

Memory-only authenticated live HTTP з трьома applied filters підтвердив `200`,
CSV content type, server filename, no-store, BOM, CRLF, 28 columns,
summary-first і event/row parity `1/2`, без forbidden columns. Browser gate на
`1440×1000`, `768×1024` і `390×844` підтвердив success/content preservation,
`0` horizontal overflow, 44px CTA та clean console.

Focused backend спочатку не бачив нові файли, бо immutable `backend-test`
image не має bind mount; точковий rebuild image відновив visibility і tests.
Mypy у stripped runtime потребував canonical `--no-sqlite-cache`. Паралельний
frontend wrapper та integrated BuildKit по одному разу впали у V8; isolated
frontend gate пройшов, Docker Desktop штатно перезапущено після missing exit
event, а production web image успішно зібрано ізольованим buildx builder.
`docker compose up -d --wait`, root/readiness `200` і актуальний frontend asset
підтвердили відновлення без видалення volumes. Browser viewport скинуто,
вкладки закрито, credentials лишилися тільки у Git-ignored `.env.local`.

Post-MVP TP-1001—TP-1012 завершені; GAP-11 і GAP-18 мають статус `resolved`.

## Етап заявок та Telegram

2026-07-28 зафіксовано
[контракт TP-1008—TP-1011](../architecture/tp-1008-1011-booking-requests-telegram-contract.md)
і [план реалізації](booking-requests-telegram-implementation-plan.md):

- TP-1008 `done`: role-scoped домен/CRM-розділ заявок і idempotent
  `NEW → PROCESSED`; ім’я, телефон, послуга й коментар клієнта необов’язкові;
  canonical `426/426` backend, `223/223` frontend, role/responsive/optional-field
  browser QA і [evidence](../evidence/tp-1008/README.md);
- TP-1009 `done`: admin rotation digest-only Bearer token, external
  server-to-server create API, Idempotency-Key і
  [integration guide](../integrations/booking-requests-api.md); canonical
  `434/434` backend, `225/225` frontend, `42/42` axe, live create/replay/mismatch,
  responsive browser QA і [evidence](../evidence/tp-1009/README.md);
- TP-1010 `done`: one-time private Telegram authorization, verified webhook,
  `/start`/`/stop`, subscription dialog і durable fan-out усім enabled
  admin/reception subscriptions; focused `25/25` booking-request backend,
  canonical `440/440` backend, `227/227` frontend, OpenAPI/types/contracts,
  production web image check і live desktop/mobile Telegram dialog QA green;
  [evidence](../evidence/tp-1010/README.md);
- TP-1011 `done`: authorized inline process callback через той самий domain
  service, `answerCallbackQuery`, first-actor idempotency, best-effort cross-chat
  `editMessageText` sync/retry, operations status command і
  [production rollout runbook](../operations/telegram-rollout-runbook.md);
  focused `29/29` booking-request backend, canonical `444/444` backend,
  `227/227` frontend, contracts/typecheck/lint/build/runtime readiness green;
  [evidence](../evidence/tp-1011/README.md).
- TP-1012 `done`: assignee-only durable Telegram delivery внутрішніх справ,
  статуси open/overdue/completed/reassigned, authorized
  `✅ Виконати справу`, exact CRM link і Telegram linking для podologist без
  розширення booking-request fan-out; focused `16/16`, canonical `450/450`
  backend, `227/227` frontend і `42/42` axe, migration/worker/beat/runtime
  readiness green; [contract](../architecture/tp-1012-work-item-telegram-contract.md)
  і [evidence](../evidence/tp-1012/README.md).

Локальна dev migration `booking_requests.0006` застосована, оновлений web image
і backend/worker/beat запущені; manual dispatch та наступний periodic cycle
green, `/health/ready` і `/` повертають `200`. Локальний Telegram token не
налаштований, active subscriptions/open work items під час gate — `0/0`,
зовнішні повідомлення не надсилались.

Production deploy TP-1012 не виконувався. Оприлюднений раніше Telegram bot
token не переносився у tracked files; перед наступним rollout він має бути
rotated, якщо це ще не зроблено, і зберігатися лише у production env/file
secret.

## Вибір дати в календарі

2026-07-29 у календарі додано CRM-styled попап вибору дати або тижня:
перемикання режиму, навігацію між місяцями, перехід до сьогодні, підсвічування
поточної дати/тижня, закриття через Escape або клік поза попапом і повернення
фокуса на кнопку дати. На мобільних попап фіксується у доступній області
екрана, а на невисоких desktop-вікнах прокручує лише власний вміст.

Canonical frontend gate green: `230/230` tests, `43/43` axe, ESLint, strict
typecheck, production build і production web image. Browser QA на
`1440×900`, `1280×720` та `390×844` підтвердив вибір дня/тижня, клавіатурну
поведінку, відсутність горизонтального overflow і коректне розміщення попапа.
Оновлений локальний web запущений; `/health/ready` і `/` повертають `200`.
Production deploy не виконувався.

## PDF-квитанція та бланк рекомендацій

2026-07-30 завершено TP-1013 за
[контрактом](../architecture/tp-1013-payment-receipt-pdf-contract.md).
Reception/admin після повної оплати отримує двосторінковий чорно-білий A4 PDF:
квитанцію з immutable payment/service snapshots та окремий бланк з актуальною
рекомендацією подолога. Clinic profile і optional logo додаються без залежності
доступності object storage; clinical notes і фото не експортуються.

`GET /api/v1/payments/{payment_id}/receipt` підтримує `attachment` для
завантаження та `inline` для друку, застосовує finance scope і повертає
`private, no-store`. У finance UI дії доступні одразу після успішної оплати та
в деталях проведеної операції. Документ прямо позначений як нефіскальна
квитанція; інтеграція РРО/ПРРО не входить у цей packet.

Gate: `454/454` backend і `231/231` frontend tests, Ruff/format, mypy,
Django checks/migrations, OpenAPI snapshot, generated client, ESLint, strict
typecheck і production build green. Poppler render підтвердив дві A4-сторінки
без обрізання; authenticated browser gate підтвердив download/print actions.
In-app browser не підтримує download handle, тому PDF bytes/content/headers
окремо підтверджені integration test і live API probe.

Після UI regression report виправлено DRF content negotiation для
`Accept: application/pdf`, який раніше повертав `406 Not Acceptable` до входу
у receipt view. Regression tests передають той самий `Accept`, що й browser
client; live `attachment` та `inline` probes повертають `200`, `%PDF-` і
очікувані headers. Footer діалогу перебудовано так, щоб на широкому екрані
текст дій не переносився; перевірено у viewport `1440×900`.

Автоматичний `print()` через прихований PDF iframe замінено на пряме відкриття
`inline` PDF у новій вкладці. Це прибирає залежність від `contentWindow` і
дозволів embedded browser; системний друк запускається зі стандартного
PDF-переглядача браузера.

Під час першого довгого combined gate Docker Desktop не повернув exit event
від test container. Окрема recovery-підзадача перевірила контейнер і bind
mounts, штатно перезапустила Docker Desktop та підтвердила мінімальний bind
і readiness. Повторні короткі backend groups, повний frontend container check,
production rebuild і `/health/ready` пройшли; volumes/domain data не
видалялися. Локальні credentials читалися лише з Git-ignored `.env.local`.

Цей checkpoint є повним release scope TP-1013: PDF-квитанція, бланк
рекомендацій, download/print UX, 406 regression fix і responsive footer.
Публікація виконується штатним `main` autodeploy; authoritative результат
фіксується GitHub Actions `Quality gate` та production health checks для
`crm.rozhenko.km.ua` без reset або зміни domain data.
