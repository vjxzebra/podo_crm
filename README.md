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
