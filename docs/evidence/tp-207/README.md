# TP-207 append-only audit infrastructure evidence

Перевірено 2026-07-21 через Docker quality gates на PostgreSQL 17. TP-207 не містить окремого UI: user-facing list/detail «Було → Стало» залишається в TP-803, а цей пакет фіксує серверний контракт і незмінність даних.

Реалізований контракт:

- `AuditEvent` має UUID, immutable actor/role snapshot, registry section/action, стабільне object reference, result, description, redacted `before/after`, note, correlation ID та UTC timestamp;
- domain service приймає лише event types із централізованого registry і вимагає активний `transaction.atomic()`;
- recursive redaction прибирає паролі, hashes, session IDs/keys, tokens, secrets, credentials, cookies та signed URLs, але зберігає безпечну password metadata на кшталт expiry/force-change flags;
- instance save/delete, queryset update/delete/bulk-update та PostgreSQL `BEFORE UPDATE OR DELETE` trigger блокують зміну події;
- admin-only endpoints підтримують search, actor/section/date filters, стабільний UUID cursor і typed list/detail projections;
- own/first-login password change, enumeration-safe reset request та admin temporary password записують подію в тій самій транзакції з mutation.

Автоматизовані докази:

- rollback після вставки не залишає audit event;
- ORM і прямий SQL не можуть змінити існуючий event;
- nested secrets редагуються до запису в PostgreSQL;
- незареєстрована action відхиляється без side effect;
- podologist/reception отримують `403`, anonymous — `401`, admin бачить actor snapshot і redacted detail;
- filter validation використовує shared `422` envelope, а 51-event fixture підтверджує межу й продовження cursor pagination;
- password lifecycle tests перевіряють actor/object і відсутність password material у подіях;
- OpenAPI snapshot і generated TypeScript client містять audit list/detail, filters, actor/object/change schemas.

AC-20 ще не позначений повністю завершеним: кожен наступний mutation packet має додати свій registry event і transactional assertion; повний admin UI та cross-domain coverage registry входять у TP-803.
