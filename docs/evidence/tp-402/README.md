# TP-402 evidence — appointment create

Дата перевірки: 2026-07-21.

## Реалізований вертикальний результат

- Transactional `POST /api/v1/appointments` копіює snapshots тривалості, послуги й кабінету та завжди стартує зі статусу `NEW`.
- Сервер перевіряє role-visible patient, active podologist/service/room, podologist-to-self, 15-хвилинну сітку, clinic-wide робочий день/перерви та complaint XOR.
- Specialist і room блокуються в транзакції; явна occupancy-перевірка та PostgreSQL exclusion constraints мапляться у стабільний `409 appointment_slot_conflict` із field context.
- UI відкривається з header CTA, вільної calendar cell або locked patient card, підтримує live patient search, inline patient create, server-managed duration/status, availability, збереження введених полів після помилки й unsaved guard.

## Автоматичні перевірки

- Canonical `scripts/run-tests.ps1`: 143 backend tests і 64 frontend tests успішні.
- Ruff format/check для 123 Python files, mypy для 97 source files, Django checks/migration drift, OpenAPI snapshot/generated TypeScript schema, contracts, lint, strict typecheck, 12 axe routes і production build успішні.
- Scheduling coverage включає admin/reception/podologist, чужого спеціаліста й пацієнта, inactive resources, complaint XOR, workday/break/grid boundaries, specialist/room conflicts та concurrent POST, де рівно один запит отримує `201`, інший — `409`.

## Live browser evidence

Live Compose stack перевірено через in-app browser з локальною authenticated admin session. Реальний appointment submit не виконувався: live QA перевірив безпечні проміжні стани, а mutation/rollback/conflict покриті автоматизованими тестами. Credentials у evidence або tracked-файли не записувалися.

| Сценарій / viewport | Файл | Результат |
|---|---|---|
| Desktop default `1280×720` | `appointment-create-desktop.png` | Header CTA відкриває повну форму; patient picker і server-managed поля видимі |
| Desktop availability | `appointment-create-availability-desktop.png` | Послуга задає 30 хв, API повертає 30 вікон, вибір 09:00 автоматично підставляє активний кабінет |
| Tablet `820×900` | `appointment-create-tablet.png` | Двоколонкова форма не має page overflow; modal має власний vertical scroll |
| Mobile `390×844` | `appointment-create-mobile.png` | Поля перебудовуються в одну колонку; modal лишається читабельним і керованим |
| Inline patient | `appointment-inline-patient.png` | Empty patient search відкриває вкладену create modal, не закриваючи appointment form |

Окремо перевірено preset 09:00 з calendar cell: після вибору послуги форма нормалізувала еквівалентні ISO `...00.000Z` / `...00Z`, вибрала 09:00 і Кабінет 1. Unsaved guard показав явне підтвердження. Console errors: `[]`; тимчасовий viewport override скинуто.
