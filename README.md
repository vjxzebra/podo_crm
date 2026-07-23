# Podoria CRM

Модульний моноліт на Django/DRF із React frontend, PostgreSQL, Redis, Celery та приватним MinIO object storage.

MVP release gate завершено 2026-07-23: `23/23` acceptance criteria verified,
full-role UAT пройдено на desktop/tablet/phone, canonical tests, fresh/populated
database, dependency/runtime-image audits, encrypted restore та production-like
deployment/rollback gates зелені. Деталі — у [TP-904 evidence](docs/evidence/tp-904/README.md).

## Локальний запуск

Потрібні Docker і Docker Compose. Значення для локальної розробки мають безпечні від production defaults, тому перший запуск не потребує `.env`:

```powershell
docker compose up --build
```

Після старту:

- застосунок: <http://localhost:8088>;
- liveness: <http://localhost:8088/health/live>;
- readiness: <http://localhost:8088/health/ready>;
- OpenAPI schema: <http://localhost:8088/api/v1/schema>;
- MinIO console: <http://localhost:9001>.

Для власних портів і credentials скопіюйте `.env.example` у `.env`. Production deployment не повинен використовувати dev defaults.

### Локальний користувач для входу

У `DEBUG` можна явно створити або оновити один тестовий профіль. Команда відмовляється працювати поза development mode і не створює default credentials автоматично.

Поточний локальний доступ до адміністративного інтерфейсу CRM зберігається в проігнорованому Git файлі `.env.local`:

- URL: <http://localhost:8088>;
- email: змінна `PODORIA_LOCAL_ADMIN_EMAIL`;
- пароль: змінна `PODORIA_LOCAL_ADMIN_PASSWORD`;
- роль: `admin`.

Ці credentials призначені виключно для локальної розробки. Не використовуйте їх у staging або production і не додавайте `.env.local` до Git. Безпечні placeholders наведені в `.env.example`. Після очищення PostgreSQL volume профіль можна відтворити командою:

```powershell
$localAccess = Get-Content .env.local -Raw | ConvertFrom-StringData

docker compose run --rm `
  -v "${PWD}/.env.local:/run/local-access/.env.local:ro" `
  backend python manage.py provision_dev_user `
  --email $localAccess["PODORIA_LOCAL_ADMIN_EMAIL"] `
  --credentials-file /run/local-access/.env.local `
  --role admin `
  --first-name Локальний `
  --last-name Адміністратор
```

Доступні ролі: `admin`, `reception`, `podologist`. Роль і список доступних маршрутів надходять тільки із `GET /api/v1/session`; frontend не є джерелом авторизації.

## Контракти API

OpenAPI snapshot зберігається в `backend/openapi/schema.json`, а типи клієнта — у
`frontend/src/api/schema.d.ts`. Після зміни API-контракту оновіть обидва артефакти:

```powershell
.\scripts\update-contracts.ps1
```

Linux/macOS: `sh ./scripts/update-contracts.sh`.

## Повний quality gate

```powershell
docker compose config
.\scripts\run-tests.ps1
```

Linux/macOS: `sh ./scripts/run-tests.sh`. Docker test profile перевіряє Ruff, форматування,
mypy, Django checks і migrations, pytest, OpenAPI snapshot, ESLint, strict TypeScript,
компонентні тести, синхронність generated client та production build.

Readiness повертає `200`, лише коли PostgreSQL, Redis і MinIO доступні. API-помилки
використовують envelope `code`, `message`, `fields`, `correlation_id`; кожна backend
відповідь містить `X-Request-ID`, а application logs пишуться як JSON.

Session authentication використовує `podoria_sessionid` (`HttpOnly`, `SameSite=Lax`; `Secure` за замовчуванням поза `DEBUG`) та окремий CSRF cookie для `X-CSRFToken` на login/logout і інших unsafe requests. TP-902 обмежує invalid login за keyed email digest і trusted-proxy IP (`5/30` спроб за 15 хвилин), завершує session після 30 хвилин бездіяльності або 12 годин absolute lifetime і повертає safe `401 session_expired`. Налаштування доступні через `LOGIN_RATE_LIMIT_*`, `SESSION_IDLE_TIMEOUT_SECONDS` і `SESSION_ABSOLUTE_TIMEOUT_SECONDS`; production startup також вимагає власний `DJANGO_SECRET_KEY`.

Proxy і direct API додають CSP, Permissions-Policy, `DENY`, `nosniff`, same-origin referrer/COOP; protected API не кешуються (`no-store`). Production defaults вмикають HTTPS redirect та one-year HSTS із subdomains. HSTS preload лишається explicit opt-in після перевірки production domain і всіх subdomains.

TP-903 додає [operations runbook](docs/operations/backup-deployment-runbook.md),
`compose.production.yaml` без source bind mounts, file-mounted secrets, окремі read-only
backup identities, encrypted PostgreSQL+MinIO recovery points, 30 daily/12 monthly retention,
isolated restore verification та image-only deployment rollback. Production HSTS preload є
explicit operator decision після підтвердження HTTPS для домену й усіх subdomains; звичайні
HTTPS redirect, one-year HSTS і subdomains лишаються обов'язковими.

Production CRM на спільному WordPress-сервері, autodeploy із `main`, guarded reset,
створення initial admin і великий cross-domain demo seed задокументовані в
[production command reference](docs/operations/production-command-reference.md).

Password lifecycle з TP-202 додає примусовий first-login для тимчасових паролів, зміну власного пароля з перевіркою поточного, enumeration-safe reset request та admin-only чергу відновлення. Тимчасовий пароль за замовчуванням діє 24 години (`TEMPORARY_PASSWORD_TTL_HOURS`); його встановлення відкликає всі сесії працівника, а зміна власного пароля зберігає лише поточну сесію.

Audit foundation з TP-207 надає admin-only `GET /api/v1/audit-events` і `GET /api/v1/audit-events/{id}`, стабільну cursor pagination, пошук/фільтри та redacted «Було → Стало». Domain services записують лише зареєстровані event types усередині `transaction.atomic()`; application API та PostgreSQL trigger забороняють update/delete. Password change, reset request і temporary password уже інтегровані з аудитом.

Team lifecycle з TP-203 додає admin-only `GET/POST /api/v1/users`, `GET/PATCH /api/v1/users/{id}` і `POST /api/v1/users/{id}/deactivate`. Профіль містить ім’я, телефон, case-insensitive unique email, одну з трьох ролей, active/first-login state і last login. Зміна ролі та деактивація відкликають сесії; row-level locking не дозволяє двом concurrent mutation прибрати останнього активного адміністратора. Responsive `/team` підтримує search/status filter, create/edit/reactivate/deactivate і temporary-password flows.

Clinic settings з TP-204 додають singleton `GET/PATCH /api/v1/clinic-profile`, authenticated private-read та admin-only upload `/api/v1/clinic-profile/logo`, а також `GET/POST /api/v1/rooms` і `PATCH /api/v1/rooms/{id}`. Профіль містить повні name/phone/email/address/description поля; PNG/JPEG до 5 МБ повністю декодується, звіряє MIME/format і dimensions, перекодовується без metadata та зберігається в private MinIO bucket. Кімнати мають case-insensitive unique name, optimistic version та active state без delete, щоб майбутні appointment зберігали історичний snapshot. Responsive `/settings` покриває profile, logo, room empty/create/deactivate/conflict states.

Service catalog з TP-205 додає authenticated `GET /api/v1/services`, `GET /api/v1/services/{id}` і admin-only `POST/PATCH`. Адміністратор керує unique code, назвою, додатною тривалістю, ціною в integer minor units, кольором календаря та active state з optimistic version; фізичного delete немає. Рецепція й подолог отримують лише активну picker-проєкцію без status/version/timestamps. Третя вкладка `/settings` має search/status filter, responsive table/cards, палітру, create/edit/deactivate/conflict states та audit для кожної mutation.

System status і clinic schedule з TP-206 додають admin-only `GET /api/v1/appointment-status-configs`, `PATCH /api/v1/appointment-status-configs/{code}` та `GET/PUT /api/v1/clinic-workdays`. Рівно вісім seeded status codes не можна змінити або видалити навіть raw SQL mutation через PostgreSQL trigger; редагуються label, color і три manual-role flags з optimistic version. Єдиний повторюваний графік `Europe/Kyiv` містить сім днів і довільну кількість перерв усередині робочих годин без overlap; bulk update атомарний і пише один before/after audit event. `/settings` не містить specialist schedule, holidays, vacations або exceptions UI.

Patient directory з TP-301 додає role-scoped `GET /api/v1/patients?search=&cursor=` та audited `POST /api/v1/patients`. Телефон нормалізується й індексується, але навмисно не є unique: UI попереджає про можливий дублікат без блокування створення. Admin/reception бачать усі safe contacts, podologist — лише власний relationship scope; список має live search, empty state, cursor pagination і responsive create form.

Patient card/edit з TP-302 і TP-605 додає `GET/PATCH /api/v1/patients/{id}`, role-safe `GET /api/v1/patients/{id}/visits`, medical-only `GET /api/v1/patients/{id}/{photos|recommendations}` та versioned `POST/PATCH /api/v1/visits/{id}/recommendations...`. Reception отримує лише адміністративні, контактні й безпечні completion-факти без clinical/photo/recommendation keys; admin бачить повну дозволену проєкцію, а podologist — тільки власні visits у межах patient scope. Completed history використовує незмінні service/cost snapshots і cursor pagination; приватні фото згруповані за visit та відкриваються короткоживучими signed URLs у доступній каруселі «До / Після». Рекомендації мають дату, автора, optimistic version conflict і atomic audit. Scoped lookup виконується до serialization та payload validation, тому чужий UUID повертає `404`; responsive `/patients/{id}/{overview|visits|photos|recommendations}` покриває loading/empty/error/retry, unsaved і mobile fullscreen states.

Internal work items з TP-303 додають authenticated `GET/POST /api/v1/work-items` і versioned `PATCH /api/v1/work-items/{id}`. Admin/reception можуть перемикати own/all scope, а podologist завжди отримує лише справи, де він відповідальний; linked patient перевіряється у межах actor scope, а справа для podologist не може посилатися на чужого пацієнта. Типи охоплюють callback, підтвердження запису, ручне повідомлення та інше; є due time, important flag і explicit complete/reopen з row lock, optimistic version та atomic audit. Responsive `/work-items` має live overview summary, search/scope/status filters і create/complete flow. «Перетелефонувати» у картці пацієнта відкриває callback із locked patient context — CRM не здійснює автоматичного дзвінка.

Inventory з TP-501—503 додає admin-only catalog `GET/POST /api/v1/inventory/materials`, `GET/PATCH /api/v1/inventory/materials/{id}`, `GET /api/v1/inventory/materials/{id}/lots`; operations `POST /api/v1/inventory/receipts`, `POST /api/v1/inventory/write-offs`; stocktake preview/create/detail/post та read-only movement journal/detail. Матеріали мають unique SKU, категорію, одиницю, мінімальний залишок та active/version state без delete; перша партія блокує зміну одиниці, а lot identity не змінюється. API проєктує total/available quantity, найближчий строк, stock status і FEFO, причому прострочені партії не входять у available. Mutations вимагають `Idempotency-Key`, блокують rows у детермінованому порядку, не допускають від'ємного залишку та створюють незмінні operation/movement rows з atomic audit. Stocktake зберігає immutable DRAFT snapshot, під час posting відхиляє змінений баланс через `409 stocktake_balance_changed`, а різниці й подальші виправлення оформлює append-only compensating movements. Responsive `/inventory` має catalog/details, надходження, ручне списання, двоетапну інвентаризацію та cursor-paginated journal із search/date/kind/material/actor filters і read-only operation detail; supplier лишається атрибутом receipt/lot без окремого довідника.

Visit workflow з TP-601—TP-605 додає `POST /api/v1/appointments/{id}/start-visit`, `GET /api/v1/visits/{id}`, visit-scoped material options, versioned `PUT /api/v1/visits/{id}`, upload-intent/finalize/private-read/draft-delete lifecycle для фото, idempotent `POST /api/v1/visits/{id}/finish` і завершений patient archive. Почати прийом можна лише з ARRIVED appointment; операція атомарно переводить його в IN_PROGRESS, створює не більше одного visit, допускає assigned podologist/admin, а безпечний повтор повертає вже створений visit без дублювання audit. Чернетка зберігає complaint XOR, examination-поля, нормалізовані service quantities, material/lot decimal quantities та стабільні snapshots без складських, фінансових або completion side effects. Крок 3 має окремі BEFORE/AFTER dropzones, progress/retry/delete та authorized previews; натискання thumbnail відкриває visit-wide popup slider із лічильником, стрілками, клавішами ←/→, `Esc`, focus trap і поверненням фокуса. JPEG/PNG/WebP до 10 МБ канонізуються без EXIF/GPS у private MinIO, мають ліміт 10 на блок і не розкривають metadata/URL reception. Finalize є replay-safe, а видалення дозволене лише до завершення прийому й атомарно пише audit. Крок 4 повторно перевіряє version, stock і optional follow-up slot під lock order appointment→visit→sorted lots; в одній транзакції завершує appointment/visit, створює `VISIT_USAGE` movements, незмінне receivable на server-derived total, рекомендацію, optional appointment та audit. Повтор із тим самим payload повертає збережений результат, а недостатній залишок, зайнятий slot або injected fault не лишають часткових записів. TP-605 проєктує завершені snapshots у хронологію, visit-grouped приватний photo archive з окремими вкладками й versioned authored recommendations; фактичне проведення оплати лишається окремим finance packet.

Finance workflow з TP-701—TP-704 додає reception/admin endpoints для відкриття/читання власної касової зміни, tagged `GET /api/v1/finance/operations`, idempotent full `POST /api/v1/payments`, full `POST /api/v1/payments/{id}/refunds`, strict `POST /api/v1/cash-movements`, authoritative `GET /api/v1/cash-shifts/{id}/close-preview`, versioned/idempotent `POST /api/v1/cash-shifts/{id}/close`, role-scoped history/detail `GET /api/v1/cash-shifts[/{id}]`, responsive `/finance` та `/finance/shifts`. У працівника може бути лише одна відкрита власна зміна; opening balance фіксовано дорівнює нулю, а всі totals, expected cash і discrepancy відтворюються з append-only ledger. Повна оплата й одне повне повернення мають server-derived amount, refund успадковує original method, cash movements не мають patient/payment-method полів, а non-zero close discrepancy потребує comment. Shift і posting services ділять один lock order, тому close-vs-payment/refund/cash races не залишають late ledger rows; CLOSED shift, reconciliation і immutable opener/closer/actor snapshots не редагуються. TP-704 пройшов 298 backend, 164 frontend і 35 axe tests; OpenAPI/types/build та dev migration `0004 → 0005 → 0004 → 0005` чисті, runtime `/finance/shifts` повертає `200`, а authenticated desktop/tablet/mobile browser gate підтвердив close/history/detail, 0 overflow, 44 px targets і clean console. [TP-704 evidence](docs/evidence/tp-704/README.md) фіксує, що user-owned OPEN shift і CARD payment збережені та live close не виконувався.

Global search з TP-801 додає authenticated `GET /api/v1/search?q=&types=` і responsive overlay для patients, appointments, payments та materials. Role/object scope застосовується до пошуку, ranking, limit і serialization; exact identifier/code/phone має пріоритет над prefix і substring matches. PostgreSQL використовує `pg_trgm` та вісім targeted GIN indexes без окремого search engine. `Ctrl/Cmd+K`, keyboard navigation, grouped loading/empty/error/retry states, focus return/body lock і mobile fullscreen підтримані; canonical patient route та appointment/payment/material query-param details відновлюються після reload і очищаються при close. TP-801 пройшов 327 backend, 174 frontend і 36 axe tests, migration reverse/reapply та read-only runtime/browser gates без зміни dev даних; [evidence](docs/evidence/tp-801/README.md).

Internal notifications з TP-802 додають recipient-only `GET /api/v1/notifications?status=all|unread&cursor=`, idempotent read/read-all endpoints і `notification_unread_count` у session. Arrival/cancel, payment-ready та password-reset events створюються після commit; щохвилинний Celery beat формує upcoming-appointment і overdue-work-item reminders. Database uniqueness `(recipient, event_key)` не допускає duplicate retries/races, а deep links обмежені role-safe local routes із `/` fallback. Responsive `/notifications` має numeric badge, all/unread filters, ordered Today/Yesterday/date groups, cursor, loading/error/retry/empty і синхронний read state. TP-802 пройшов 340 backend, 180 frontend і 37 axe tests, migration/runtime/worker/beat та authenticated desktop/tablet/mobile gates; [evidence](docs/evidence/tp-802/README.md).

Admin audit UI з TP-803 завершує TP-207 foundation: responsive `/audit` доступний лише адміністратору, фільтрує події за пошуком, працівником, розділом і точною датою, має cursor pagination та reload-stable `?event=<uuid>` detail. Деталь показує історичні actor/object snapshots, result, description, correlation ID і кожну redacted зміну як «Було → Стало»; object links обмежені allowlist, а edit/delete/export відсутні. Registry completeness test звіряє всі `AuditAction`, date range validation повертає `422`, інші ролі не бачать route і отримують server denial. TP-803 пройшов 342 backend, 187 frontend і 38 axe tests, migration-free/runtime та authenticated desktop/tablet/mobile gates; [evidence](docs/evidence/tp-803/README.md).
