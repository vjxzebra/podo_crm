# TP-602 — послуги й матеріали в чернетці візиту

Дата перевірки: 2026-07-21.

## Реалізований зріз

- Visit draft зберігає нормалізовані `service_lines` і `material_lines` через versioned `PUT /api/v1/visits/{visit_id}`; один успішний save збільшує version один раз і створює один `VISIT_DRAFT_SAVED` audit.
- Основна послуга appointment автоматично стає primary line. Повторне додавання послуги збільшує integer quantity, а код, назва, тривалість і ціна фіксуються snapshot-полями.
- Material picker `GET /api/v1/visits/{visit_id}/material-options?search=` повертає лише active materials з придатними партіями в FEFO-порядку, не розкриваючи закупівельну ціну чи постачальника.
- Material line зберігає lot/material/expiry snapshots і фактичну decimal quantity. Draft перевіряє поточну доступність, але не створює `InventoryOperation`/`StockMovement` і не змінює залишок; повторна перевірка та списання належать `finish_visit` у TP-604.
- Assigned podologist/admin мають object scope; reception отримує `403`, foreign podologist — scoped `404`. Невалідні, stale та audit-fault mutations не залишають частково замінених рядків.
- Крок 2 visit workspace має пошук, loading/error/empty states, quantity controls, remove, totals, material dialog, FEFO lot selection, insufficient-stock validation, autosave/manual save й unsaved guard.

## Browser gate

Перевірка виконана у вбудованому браузері на локальному production Compose stack без submit. Перед очищенням підтверджено `version=1`, два service lines, один material line, `VISIT_DRAFT_SAVED=0`, `InventoryOperation=0` і `StockMovement=0`; після перевірки всі точні visit/appointment/patient/room/service/material/lot fixtures видалені.

| Viewport | Перевірено | Результат | Артефакт |
|---|---|---|---|
| Desktop `1280×720` | seeded primary/additional services, quantities, totals і material line | page overflow `0`; усі основні блоки в межах viewport | [visit-lines-desktop.png](visit-lines-desktop.png) |
| Tablet `834×1000` | material search, selection і FEFO lot picker | dialog `760px`, page overflow `0`, Add доступна для фактичної кількості | [material-picker-tablet.png](material-picker-tablet.png) |
| Mobile `390×844` | service search/results/cards та quantity controls | page overflow `0`; рядки `327.6px`; мінімальна interactive height `44px`; steps мають власний intentional scroll | [visit-lines-mobile.png](visit-lines-mobile.png) |

Console errors: `0`. Console warnings: `0`.

## Автоматизовані докази

- Backend: `backend/tests/visits/test_visit_draft_lines.py` — 8 TP-602 сценаріїв для snapshots/totals/dedup, FEFO/redaction/scope, availability/no-side-effects, rollback та OpenAPI.
- Frontend: 5 TP-602 component-сценаріїв у `frontend/src/App.test.tsx` і material-picker axe scenario у `frontend/src/app/accessibility.test.tsx`.
- Під час точкового очищення виявлено deferred-field recursion у `MaterialLot.from_db`; виправлення захищене регресійним тестом `test_deferred_material_lot_fields_do_not_recurse_and_still_protect_identity`.
- Canonical `scripts/run-tests.ps1`: 201 backend tests, 98 frontend tests, 21 axe scenarios, Ruff/format для 155 Python files, mypy для 121 source files, Django checks/migrations, OpenAPI/generated client/contracts, lint, strict typecheck і production Vite build — green.
