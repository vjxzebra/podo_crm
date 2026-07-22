# TP-501 — material/lot catalog evidence

Дата перевірки: 2026-07-21.

## Реалізований scope

- admin-only каталог матеріалів із пошуком, категорією, станом запасу й active-фільтром;
- create/edit/deactivate/reactivate без фізичного delete, optimistic `version` та atomic audit;
- незмінна одиниця виміру після першої партії, case-insensitive незмінна ідентичність партії;
- total/available/expiry projections, виключення прострочених партій із available та FEFO-порядок;
- read-only деталі партій; надходження і ручне списання лишаються TP-502;
- supplier зберігається як атрибут партії, окремого supplier module/tab немає.

## Browser gate

| Viewport | Перевірено | Результат |
|---|---|---|
| `1280×720` | каталог і modal деталей | page/dialog overflow `0`; FEFO та unavailable expired lot видимі |
| `768×1024` | toolbar і table scroller | page overflow `0`; controls `44px`; таблиця прокручується лише всередині |
| `390×844` | mobile modal і lot cards | page/dialog overflow `0`; close/action targets `44px` |

Console errors/warnings: `0`. Тимчасові browser fixtures видалені після перевірки; readiness повернув `200`.

## Артефакти

- [desktop details](inventory-details-desktop.png)
- [tablet catalog](inventory-catalog-tablet.png)
- [mobile details](inventory-details-mobile.png)
- backend: `backend/tests/inventory/test_material_catalog.py`;
- frontend: TP-501 scenarios у `frontend/src/App.test.tsx` і route у `frontend/src/app/accessibility.test.tsx`.

Канонічний `scripts/run-tests.ps1`: 161 backend tests, 75 frontend tests, 14 axe scenarios, Ruff/format, MyPy, migrations, OpenAPI snapshot/generated client, lint, strict typecheck і production build — пройдені.
