# TP-802 — internal notifications

Статус: `done` 2026-07-22.

## Реалізований зріз

- Recipient-owned `Notification` має UUID, стабільний `(recipient, event_key)` idempotency key, immutable message/deep-link metadata та nullable `read_at`; selector завжди починається з поточного recipient.
- `GET /api/v1/notifications?status=all|unread&cursor=`, `POST /api/v1/notifications/{id}/read` і `POST /api/v1/notifications/read-all` реалізують cursor list, unread count і idempotent read state. `GET /api/v1/session` повертає початковий `notification_unread_count` для badge.
- Immediate `on_commit()` events охоплюють arrival/cancel, visit payment handoff і password-reset request. Celery beat щохвилини запускає upcoming-appointment та overdue-work-item reminders; повторний або concurrent dispatch не створює дубліката.
- Deep links є лише relative local routes, повторно перевіряються за route scope recipient і мають безпечний `/` fallback.
- Responsive `/notifications` підтримує all/unread filters, today/yesterday/date groups, loading/error/retry/empty, cursor pagination, item read, mark-all і синхронний numeric shell badge.

## Automated gates

- canonical: `340/340` backend, `180/180` frontend і `37/37` axe;
- focused notifications + session: `21/21` backend;
- Ruff/format, mypy, Django system/migration checks, OpenAPI snapshot/generated TypeScript schema, contracts, ESLint, strict typecheck і production build — green;
- scope/redaction, inactive recipients, safe routes, API authentication, idempotent duplicate/concurrent dispatch, due reminders і domain-event hooks покриті tests.

## Migration і runtime

`notifications.0001_initial` пройшла forward, reverse/data-preservation і reapply gates; фінально вона applied, а `migrate --plan` не має pending operations. PostgreSQL constraints захищають recipient/event uniqueness, non-empty event key, relative deep link і порядок `created_at ≤ read_at`.

Backend, web і proxy healthy; worker і beat running. Beat надсилав `apps.notifications.tasks.dispatch_due_notification_reminders` щохвилини, worker виконував task успішно без retry/error. Runtime `/notifications` і `/health/ready` повернули `200`, unauthenticated notification API — `401`.

Під час canonical frontend gate Docker Desktop утримував ESLint process у kernel D-state. Перевірка process/container/kernel state виключила disk pressure; штатний restart Docker Desktop і точковий recreate stack відновили компонент. Мінімальний lint, повний frontend gate і фінальна production web image після цього стабільно пройшли.

## Authenticated browser evidence

На `1440×900`, `1024×768` і `390×844` перевірені ordered Today/Yesterday groups, unread badge `2 → 1 → 0`, item read, mark-all, unread empty state та відсутність horizontal page overflow. Після виявленого browser gate сортування груп виправлено й зафіксовано component regression test. Console warnings/errors відсутні; viewport скинуто, вкладку закрито. Два точні evidence notifications залишені прочитаними в локальній dev-історії.

- [Desktop notifications](notifications-desktop.png)
- [Tablet notifications](notifications-tablet.png)
- [Mobile notifications](notifications-mobile.png)
