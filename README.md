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
- MinIO console: <http://localhost:9001>.

Для власних портів і credentials скопіюйте `.env.example` у `.env`. Production deployment не повинен використовувати dev defaults.

## Перевірки TP-101

```powershell
docker compose config
docker compose run --rm backend pytest
```

Readiness повертає `200`, лише коли PostgreSQL, Redis і MinIO доступні. Кожна HTTP-відповідь backend містить `X-Request-ID`, а application logs пишуться як JSON.
