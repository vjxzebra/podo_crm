# TP-502 — receipt and manual write-off evidence

Дата перевірки: 2026-07-21.

## Реалізований scope

- admin-only `POST /api/v1/inventory/receipts` для multi-line надходження та `POST /api/v1/inventory/write-offs` для ручного списання;
- обов'язковий `Idempotency-Key`: повтор того самого payload повертає проведену операцію, інший payload з тим самим ключем — стабільний `409`;
- детермінований порядок row locks, повна транзакційна валідація до mutation і конкурентне списання без від'ємного залишку;
- незмінні проведені `InventoryOperation`/`StockMovement` на model/queryset та PostgreSQL trigger рівнях;
- atomic audit для надходження й ручного списання; rollback/conflict не залишає рухів або audit events;
- responsive multi-line receipt і manual write-off форми з доступним залишком, причиною, conflict/retry та unsaved guards;
- stocktake і журнал рухів лишаються TP-503.

## Browser gate

| Viewport | Перевірено | Результат |
|---|---|---|
| `1280×720` | дворядкове надходження, ціна/постачальник/дата, idempotency hint | page/dialog overflow `0`; обидва рядки та footer не обрізані |
| `768×1024` | tablet reflow дворядкового надходження | horizontal overflow `0`; усі 24 controls `44px`; existing-lot пояснення не переповнює grid |
| `390×844` | ручне списання з доступним залишком, кількістю, причиною й коментарем | horizontal overflow `0`; dialog уміщується без internal scroll; усі 6 controls `44px` |

Console errors/warnings: `0`. Під час browser gate операції не проводилися. Дві точні demo-картки й дві demo-партії після перевірки видалені; залишок fixtures `0/0`, readiness повернув `200`.

## Артефакти

- [desktop receipt](receipt-desktop.png)
- [tablet receipt](receipt-tablet.png)
- [mobile write-off](writeoff-mobile.png)
- backend: `backend/tests/inventory/test_inventory_operations.py`;
- frontend: TP-502 scenarios у `frontend/src/App.test.tsx` і receipt/write-off axe scenarios у `frontend/src/app/accessibility.test.tsx`.

Канонічний `scripts/run-tests.ps1`: 170 backend tests, 81 frontend tests, 16 axe scenarios, Ruff/format, MyPy, clean migrations, OpenAPI snapshot/generated client, lint, strict typecheck і production build — пройдені.
