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

У `DEBUG` можна явно створити або оновити один тестовий профіль. Команда відмовляється працювати поза development mode і не створює default credentials автоматично:

```powershell
docker compose run --rm backend python manage.py provision_dev_user `
  --email admin@podoria.local `
  --password "replace-for-local-use" `
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
