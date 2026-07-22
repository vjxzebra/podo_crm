# TP-503 — stocktake and movement journal evidence

Дата перевірки: 2026-07-21.

## Реалізований scope

- admin-only preview/create/detail/post workflow через `GET /api/v1/inventory/stocktakes/preview`, `POST /api/v1/inventory/stocktakes`, `GET /api/v1/inventory/stocktakes/{id}` і `POST /api/v1/inventory/stocktakes/{id}/post`;
- immutable DRAFT snapshot системних залишків, собівартості та фактичної кількості з обов'язковим `Idempotency-Key` на create/post;
- повторне блокування stocktake і lot rows під час posting, stale-balance `409 stocktake_balance_changed` без часткового mutation та повна транзакційна rollback-гарантія;
- append-only `STOCKTAKE_ADJUSTMENT` movements для надлишків/нестач, проведений stocktake read-only, а виправлення оформлюється новою інвентаризацією;
- cursor-paginated read-only journal через `GET /api/v1/inventory/movements` із search/date/kind/material/actor filters і деталями операції через `GET /api/v1/inventory/operations/{id}`;
- atomic `stocktake.created`/`stocktake.posted` audit, role guards і незмінність snapshot/posting rows на application та PostgreSQL trigger рівнях;
- responsive stocktake й movement journal UI з validation, difference/valuation, stale/retry, unsaved/draft guards і read-only detail.

## Browser gate

| Viewport | Перевірено | Результат |
|---|---|---|
| `1280×720` | stocktake для трьох партій; surplus `+2`, shortage `−3`, оцінка різниці `−3.20 UAH` | snapshot, фактичні значення, різниці й footer доступні без submit |
| `834×1000` | movement journal, search/date/kind/material/actor filters, read-only стан та empty result | toolbar і таблиця коректно перебудовані для tablet |
| `390×844` | stocktake у mobile card layout | 3 рядки; horizontal overflow `0` (`scrollWidth=375`, `clientWidth=375`) |

Console errors/warnings: `0`. Під час browser gate stocktake не створювався і не проводився. Точні тимчасові fixtures після перевірки видалені; залишок material/lot fixtures `0/0`.

## Артефакти

- [desktop stocktake](browser-stocktake-desktop.png)
- [tablet movement journal](browser-movement-journal-tablet.png)
- [mobile stocktake](browser-stocktake-mobile.png)
- backend: `backend/tests/inventory/test_stocktakes_and_movements.py` — 13 TP-503 scenarios;
- frontend: TP-503 scenarios у `frontend/src/App.test.tsx` і stocktake/journal axe scenarios у `frontend/src/app/accessibility.test.tsx`.

Канонічний `scripts/run-tests.ps1`: 183 backend tests, 86 frontend tests, 18 axe scenarios, Ruff/format для 141 Python files, MyPy для 110 source files, Django checks/clean migrations, OpenAPI snapshot/generated client, contracts, lint, strict typecheck і production build — пройдені.
