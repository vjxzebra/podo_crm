# TP-1014—TP-1021 — evidence виконання CRM-допрацювань

- Дата: `2026-08-06`
- Статус: `done`
- Контракт: [TP-1014—TP-1021](../../architecture/tp-1014-1021-crm-improvements-contract.md)
- План: [AI development plan](../../planning/tp-1014-1021-ai-development-plan.md)

## Реалізований scope

- Multi-service follow-up із ordered unique `service_ids`, aggregate duration,
  legacy primary service та idempotent appointment lines.
- Порожнє поле `Рекомендована дата наступного візиту` для заповнення ручкою на
  другій сторінці PDF-квитанції.
- Одна каса `main` на клініку, одна OPEN-зміна, owner-only касові mutations і
  автоматичний carry-forward фактичного closing balance.
- Exact-recipient доставка внутрішніх `Notification` у Telegram через durable
  outbox, retry/backoff і failure isolation.
- Admin-каталог знижок 1–99%, singleton loyalty policy та кожен N-й новий
  успішно завершений візит без backfill старої історії.
- Одна несумована знижка, podologist/reception override до settlement,
  canonical gross/discount/net pricing та immutable payment/receipt snapshots.

## Автоматизовані gates

Фінальний `scripts/run-tests.ps1` завершився з exit code `0`:

- backend: `515/515` tests;
- frontend: `243/243` tests, зокрема `44/44` accessibility scenarios;
- Ruff lint і format check: `327` Python files;
- mypy: `243` source files;
- Django system check і `makemigrations --check`;
- OpenAPI snapshot та generated TypeScript client;
- ESLint, strict TypeScript і Vite production build.

Окремо перевірені migration executor, expand/contract compatibility,
PostgreSQL cash/pricing guards, raw-SQL rejection, lock order, concurrency,
idempotent finish/loyalty ordinal, exact-recipient Telegram delivery та
cross-feature finish → payment → receipt сценарій.

## PDF, browser і runtime

- PDF відрендерений Poppler як рівно дві A4-сторінки; нове поле розташоване
  після рекомендацій, текст і discount row не обрізаються та не перекриваються.
- Settings UI перевірений на desktop `1440×900`, tablet `768×1024` і mobile
  `390×844`; горизонтального page overflow немає.
- Після runtime recovery authenticated finance UI показав чинну OPEN-зміну та
  дві операції без error/retry state; API `cash-shifts/current` і
  `finance/operations` повернули `200`.
- Центр сповіщень показав лише recipient-scoped записи поточного користувача;
  browser console errors відсутні.
- Backend, worker і beat запущені з immutable image без нестабільного host
  bind-mount; worker має зареєстровану notification Telegram delivery task.
- Після одного ізольованого Docker virtual-network handshake stall до
  PostgreSQL у тимчасовий runtime override додано `PGCONNECT_TIMEOUT=5`.
  Post-fix soak дав `13/13` readiness `200` за 125,4 секунди, 5–24 мс,
  restart count `0`, два стабільні Gunicorn workers і чисті runtime logs.

Screenshots:

- [Каталог знижок — desktop](discount-settings-desktop.png)
- [Каталог знижок — tablet](discount-settings-tablet.png)
- [Каталог знижок — mobile](discount-settings-mobile.png)
- [Поточна каса — desktop](finance-desktop.png)
- [Поточна каса — mobile](finance-mobile.png)
- [Персональні сповіщення — desktop](notifications-desktop.png)

## Відновлення локальних компонентів

Відповідно до `AGENTS.md` окремими recovery-підзадачами діагностовано й
відновлено Docker Desktop після partial hang, Poppler wrapper після втрати
`%~dp0`, transient Vitest worker teardown, повторюваний Docker bind-filesystem
`EIO` та один завислий TCP handshake у новому `psycopg.connect()`. PostgreSQL
не мав blocked sessions, lock waits, deadlocks або saturation; 10 контрольних
connect+query probes тривали 5–12 мс. Volumes, dev domain data і migration
history не скидалися; кожне відновлення завершувалося повторним probe/soak.

## Межі release

- Production deployment не виконувався.
- Зовнішні Telegram-повідомлення не надсилалися; transport у tests mocked.
- Локальні credentials зберігаються лише в Git-ignored `.env.local` і не
  включені до evidence або tracked documentation.
- Дані клієнтів, Telegram chat IDs, tokens і паролі у tracked artifacts не
  фіксувалися.
