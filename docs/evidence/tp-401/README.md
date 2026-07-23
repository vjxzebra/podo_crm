# TP-401 evidence — calendar and availability

Дата перевірки: 2026-07-21.

## Реалізований вертикальний результат

- PostgreSQL `Appointment` з UTC `DateTimeRangeField`, snapshots тривалості/послуги/кабінету та partial exclusion constraints для одночасної зайнятості спеціаліста або кабінету.
- Role-scoped `GET /api/v1/calendar` і `GET /api/v1/appointments/availability`; podologist отримує лише власний календар, admin/reception — активних podologists.
- Availability враховує clinic-wide робочий день, перерви, тривалість активної послуги, зайнятість спеціаліста та вибраного активного кабінету з кроком 15 хвилин.
- Responsive day/week UI з loading/error/retry/closed/empty states, specialist filter для admin/reception і внутрішнім horizontal scroll без page overflow.

## Автоматичні перевірки

- Canonical `scripts/run-tests.ps1`: 134 backend tests і 58 frontend tests успішні.
- Ruff format/check, mypy (96 source files), Django checks/migration drift, OpenAPI snapshot/generated TypeScript schema, frontend contracts/lint/strict typecheck, 11 axe routes і production build успішні.
- Scheduling coverage: specialist/room overlap constraints, concurrent events, role scope, workday/break boundaries, resource occupancy, closed-day/foreign-podologist та validation/auth responses.

## Live browser evidence

Live Compose stack перевірено через in-app browser з локальною authenticated admin session. Тестові записи мають однаковий час, різних спеціалістів і різні кабінети; credentials у evidence або tracked-файли не записувалися.

| Viewport | Файл | Результат |
|---|---|---|
| Desktop `1440×900` | `calendar-desktop-1440x900.png` | Дві паралельні картки в окремих specialist columns; page overflow відсутній |
| Tablet `768×1024` | `calendar-tablet-768x1024.png` | Toolbar у viewport; календар скролиться лише всередині |
| Mobile `390×844` | `calendar-mobile-390x844.png` | Mobile navigation видима; сторінка не має horizontal overflow |

Окремо перевірено week view: 7 day columns, 2 event cards, внутрішній scroll `375/1470`, page overflow відсутній. Console errors і warnings: `[]`.
