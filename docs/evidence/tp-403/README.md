# TP-403 evidence — appointment detail and workflow

Дата перевірки: 2026-07-21.

## Реалізований вертикальний результат

- Role-scoped `GET /api/v1/appointments/{id}` повертає повний запис, `allowed_status_transitions` і capability flags; podologist бачить лише власні записи через selector-level safe `404`.
- `PATCH /api/v1/appointments/{id}` вимагає `version`, блокує рядок, розрізняє edit/reschedule audit, переписує snapshots при зміні ресурсів і виключає поточний запис із occupancy-перевірки.
- `POST .../status` реалізує явну transition table, manual-role flags, past-only `NO_SHOW`, terminal guards та заборону visit-managed `IN_PROGRESS`/`COMPLETED`.
- `POST .../cancel` вимагає причину, атомарно фіксує audit і переводить запис у `CANCELED`; partial exclusion constraints після цього звільняють specialist/room slot.
- UI відкриває подію календаря як доступний dialog, показує server-allowed status actions та окремі edit/reschedule/cancel стани. Slot conflict не стирає вибрані ресурси й оновлює availability.

## Автоматичні перевірки

- Canonical `scripts/run-tests.ps1`: 153 backend tests і 68 frontend tests успішні.
- Ruff format/check для 125 Python files, mypy для 98 source files, Django checks/migrations, OpenAPI validation/snapshot, generated TypeScript contract, ESLint, strict typecheck, 13 axe scenarios і production build успішні.
- Нові scheduling tests покривають admin/reception/podologist scope, detail capabilities, content edit, stale version, snapshot/duration reschedule, conflict rollback, status chain, past-only no-show, terminal lock, role forbiddance, required cancellation reason, slot release та concurrent PATCH, де рівно один запит отримує `200`, інший — `409`.
- OpenAPI contract окремо доводить required `version` для PATCH/status/cancel і required cancel reason.

## Live browser evidence

Live Compose stack перевірено через in-app browser з локальною authenticated admin session. З міркувань безпеки browser QA не надсилав зміни медичного запису й не підтверджував status/cancel; ці mutations, audit і rollback покриті автоматизованими API/component tests. Credentials у evidence або tracked-файли не записувалися.

| Сценарій | Файл | Результат |
|---|---|---|
| Detail | `appointment-detail.png` | Актуальні patient/time/service/specialist/room/status дані та server-allowed actions відображаються без помилок |
| Edit | `appointment-edit.png` | Complaint XOR і comment форма завантажують поточні значення; submit disabled без змін |
| Reschedule | `appointment-reschedule.png` | Поточний слот відокремлений від нового specialist/service/date/time/room вибору |
| Reschedule slot | `appointment-reschedule-slot.png` | Реальна availability виключає зайнятий поточний інтервал; вибір 11:00 автоматично активує Кабінет 1/2 і підставляє перший |
| Cancel confirmation | `appointment-cancel.png` | Окремий destructive state пояснює slot release, terminal history та вимагає причину |

Console errors: `0`; stack після production rebuild healthy, `/health/ready` повертає `200`.
