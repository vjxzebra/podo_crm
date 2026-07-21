# Podoria CRM

Модульний моноліт на Django/DRF із React frontend, PostgreSQL, Redis, Celery та приватним MinIO object storage.

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

docker compose run --rm backend python manage.py provision_dev_user `
  --email $localAccess["PODORIA_LOCAL_ADMIN_EMAIL"] `
  --password $localAccess["PODORIA_LOCAL_ADMIN_PASSWORD"] `
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

Session authentication використовує `podoria_sessionid` (`HttpOnly`, `SameSite=Lax`; `Secure` за замовчуванням поза `DEBUG`) та окремий CSRF cookie для `X-CSRFToken` на login/logout і інших unsafe requests.

Password lifecycle з TP-202 додає примусовий first-login для тимчасових паролів, зміну власного пароля з перевіркою поточного, enumeration-safe reset request та admin-only чергу відновлення. Тимчасовий пароль за замовчуванням діє 24 години (`TEMPORARY_PASSWORD_TTL_HOURS`); його встановлення відкликає всі сесії працівника, а зміна власного пароля зберігає лише поточну сесію.

Audit foundation з TP-207 надає admin-only `GET /api/v1/audit-events` і `GET /api/v1/audit-events/{id}`, стабільну cursor pagination, пошук/фільтри та redacted «Було → Стало». Domain services записують лише зареєстровані event types усередині `transaction.atomic()`; application API та PostgreSQL trigger забороняють update/delete. Password change, reset request і temporary password уже інтегровані з аудитом.

Team lifecycle з TP-203 додає admin-only `GET/POST /api/v1/users`, `GET/PATCH /api/v1/users/{id}` і `POST /api/v1/users/{id}/deactivate`. Профіль містить ім’я, телефон, case-insensitive unique email, одну з трьох ролей, active/first-login state і last login. Зміна ролі та деактивація відкликають сесії; row-level locking не дозволяє двом concurrent mutation прибрати останнього активного адміністратора. Responsive `/team` підтримує search/status filter, create/edit/reactivate/deactivate і temporary-password flows.

Clinic settings з TP-204 додають singleton `GET/PATCH /api/v1/clinic-profile`, authenticated private-read та admin-only upload `/api/v1/clinic-profile/logo`, а також `GET/POST /api/v1/rooms` і `PATCH /api/v1/rooms/{id}`. Профіль містить повні name/phone/email/address/description поля; PNG/JPEG до 5 МБ зберігається в private MinIO bucket. Кімнати мають case-insensitive unique name, optimistic version та active state без delete, щоб майбутні appointment зберігали історичний snapshot. Responsive `/settings` покриває profile, logo, room empty/create/deactivate/conflict states.

Service catalog з TP-205 додає authenticated `GET /api/v1/services`, `GET /api/v1/services/{id}` і admin-only `POST/PATCH`. Адміністратор керує unique code, назвою, додатною тривалістю, ціною в integer minor units, кольором календаря та active state з optimistic version; фізичного delete немає. Рецепція й подолог отримують лише активну picker-проєкцію без status/version/timestamps. Третя вкладка `/settings` має search/status filter, responsive table/cards, палітру, create/edit/deactivate/conflict states та audit для кожної mutation.

System status і clinic schedule з TP-206 додають admin-only `GET /api/v1/appointment-status-configs`, `PATCH /api/v1/appointment-status-configs/{code}` та `GET/PUT /api/v1/clinic-workdays`. Рівно вісім seeded status codes не можна змінити або видалити навіть raw SQL mutation через PostgreSQL trigger; редагуються label, color і три manual-role flags з optimistic version. Єдиний повторюваний графік `Europe/Kyiv` містить сім днів і довільну кількість перерв усередині робочих годин без overlap; bulk update атомарний і пише один before/after audit event. `/settings` не містить specialist schedule, holidays, vacations або exceptions UI.

Patient directory з TP-301 додає role-scoped `GET /api/v1/patients?search=&cursor=` та audited `POST /api/v1/patients`. Телефон нормалізується й індексується, але навмисно не є unique: UI попереджає про можливий дублікат без блокування створення. Admin/reception бачать усі safe contacts, podologist — лише власний relationship scope; список має live search, empty state, cursor pagination і responsive create form.

Patient card/edit з TP-302 додає `GET/PATCH /api/v1/patients/{id}` і окремі response projections. Reception отримує лише адміністративні та контактні поля без medical/photo keys; admin і podologist у дозволеному object scope отримують `medical_profile` та безпечні visit/photo metadata shells. Scoped lookup виконується до serialization і payload validation, тому чужий UUID однаково повертає `404` для GET/PATCH. Редагування блокує patient row, атомарно зберігає safe/medical поля та `PATIENT_UPDATED` before/after audit. Responsive `/patients/{id}/{overview|visits|photos}` має header, appointment locked-context link, loading/error/not-found, role-safe overview, history/photo shells і unsaved edit guard; реальні visits/photos/recommendations підключаються у TP-601—605.

Internal work items з TP-303 додають authenticated `GET/POST /api/v1/work-items` і versioned `PATCH /api/v1/work-items/{id}`. Admin/reception можуть перемикати own/all scope, а podologist завжди отримує лише справи, де він відповідальний; linked patient перевіряється у межах actor scope, а справа для podologist не може посилатися на чужого пацієнта. Типи охоплюють callback, підтвердження запису, ручне повідомлення та інше; є due time, important flag і explicit complete/reopen з row lock, optimistic version та atomic audit. Responsive `/work-items` має live overview summary, search/scope/status filters і create/complete flow. «Перетелефонувати» у картці пацієнта відкриває callback із locked patient context — CRM не здійснює автоматичного дзвінка.
