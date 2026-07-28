# TP-1008 — реєстр заявок на запис

Статус: `done` 2026-07-28.

## Реалізований scope

- Додано домен `booking_requests`, міграцію та immutable contact payload для
  заявок з Instagram, Facebook і сайту.
- Поля форми клієнта `client_name`, `phone`, `service` і `message` є
  необов’язковими. Реєстр і detail мають явні безпечні fallback-значення для
  кожного порожнього поля.
- Внутрішні endpoints списку, detail і `process` мають stable cursor,
  status/source/search filters, counts, optimistic version, row lock,
  idempotent повторне натискання та PII-safe audit.
- `/booking-requests` доступний лише admin/reception: desktop table, mobile
  cards, loading/empty/error/retry/load-more states, reload-stable detail і
  `NEW → PROCESSED` без перезавантаження сторінки.
- Podologist не отримує route id, не бачить пункт меню, а прямий перехід
  завершується role-safe redirect.
- External Bearer create API, rotation token у settings і Telegram навмисно не
  входять у TP-1008; це scope TP-1009—TP-1011.

## Автоматизовані gates

- `11` backend booking-request scenarios і `8` frontend component scenarios.
- Canonical: `426/426` backend і `223/223` frontend; `42` accessibility
  scenarios.
- Ruff/format, mypy, Django checks, migration check, OpenAPI snapshot,
  generated TypeScript schema, contracts, ESLint, strict typecheck і
  production build — green.
- Міграцію перевірено forward, reverse і повторним forward застосуванням.
- Регресійний тест окремо фіксує безпечне завантаження deferred model fields
  без рекурсії зі збереженням immutable guard.

## Browser QA

- Admin побачив `4` синтетичні заявки; після натискання
  `Заявка оброблена` counts змінилися `3/1 → 2/2`, у detail з’явилися
  виконавець і час, а повторна action зникла.
- Reception бачить route і відкриває реєстр.
- Podologist не бачить route; direct URL перенаправляється на
  `/?notice=forbidden`.
- На `390×844` таблиця переходить у картки, filters і counts лишаються
  доступними, а `Заявки` присутні в меню `Ще`.
- Окрема заявка лише з технічним `source` підтвердила, що ім’я, телефон,
  послуга й коментар не вимагаються та відображаються як «не вказано»; `tel:`
  link для порожнього телефону не створюється, console чиста.
- Тимчасовий viewport скинуто, локальну admin-сесію відновлено.

Артефакти:

- [desktop detail](booking-request-detail-desktop.png)
- [desktop processed state](booking-request-processed-desktop.png)
- [mobile list](booking-requests-mobile.png)
- [optional customer fields](booking-request-optional-fields.png)

## Runtime recovery

Під час фінального gate Docker test profile завис на PostgreSQL query і daemon
не отримав exit event тестового контейнера. Стан контейнерів, процесу та
`pg_stat_activity` перевірено; після штатного restart Docker Desktop точний
test container/test database прибрано, `docker compose up -d --wait` повернув
усі сервіси в healthy, а `/health/ready` — `200`. Цільовий regression test і
повний canonical gate після відновлення пройшли.

Після перезавантаження ПК Docker Desktop та production stack відновлено,
міграції повторно перевірено, web image з актуальними змінами перезібрано,
усі сервіси повернуто в healthy. Тимчасову browser-заявку видалено; її один
append-only audit event збережено за правилами журналу.

## Final hygiene

- `git diff --check` — green.
- Prefix оприлюдненого Telegram bot token у workspace — `0` збігів; tracked
  bot-token candidates — `0`.
- `.env.local` ігнорується Git. Тимчасову credentials-копію в контейнері
  видалено й перевірено.
- Реальний Telegram bot token не переносився в код, fixtures, docs або
  screenshots.
