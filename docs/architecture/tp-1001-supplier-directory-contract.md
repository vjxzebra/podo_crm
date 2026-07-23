# TP-1001 — Довідник постачальників і прив’язка надходжень

Дата фіксації: 2026-07-23

Статус: `done` 2026-07-23. [Evidence](../evidence/tp-1001/README.md).

## 1. Межа packet

TP-1001 є першим post-MVP packet і закриває відкладений `GAP-11`:

- адміністратор веде окремий довідник постачальників;
- активного постачальника можна вибрати в кожному рядку надходження;
- проведена партія зберігає незмінний snapshot назви постачальника;
- деактивація не змінює історичні партії та складські рухи;
- reception і podologist не мають доступу до API або UI довідника.

Purchase orders, accounts payable, договори, файли, імпорт та export не входять до
TP-1001.

## 2. Supplier

`Supplier` має поля:

- `id` — UUID;
- `name` — обов’язкова case-insensitive unique назва до 180 символів;
- `contact_name`, `phone`, `email`, `address`, `note` — необов’язкові контактні дані;
- `is_active` — доступність для нових надходжень;
- `version` — optimistic concurrency version;
- `created_at`, `updated_at`.

Видалення через business API відсутнє. `PATCH` із поточною `version` редагує,
деактивує або повторно активує запис. Конфлікт назви повертає
`409 supplier_name_already_exists`, stale update — `409 stale_version`.

## 3. API та RBAC

- `GET /api/v1/inventory/suppliers?search=&status=` — admin-only list;
- `POST /api/v1/inventory/suppliers` — admin-only create;
- `GET /api/v1/inventory/suppliers/{supplier_id}` — admin-only detail;
- `PATCH /api/v1/inventory/suppliers/{supplier_id}` — admin-only update/deactivate/reactivate.

Усі mutation виконуються в transaction і записують append-only audit event з
before/after snapshot. Anonymous отримує `401`, reception/podologist — `403`.

## 4. Інтеграція з партіями та надходженнями

`MaterialLot` отримує nullable `supplier_id` з `PROTECT`. Існуюче
`supplier_name` залишається історичним snapshot і не обчислюється під час читання.

Рядок `POST /api/v1/inventory/receipts` приймає optional `supplier_id`. Сервер:

1. перевіряє, що supplier існує й активний;
2. не приймає одночасно непорожні `supplier_id` та legacy `supplier_name`;
3. для нової партії записує FK та актуальну назву в snapshot;
4. для поповнення існуючої партії вимагає збігу supplier identity та snapshot;
5. зберігає backward compatibility для старих клієнтів із `supplier_name` без FK.

Data migration створює supplier records з унікальних непорожніх legacy
`supplier_name` і прив’язує наявні партії без зміни їх snapshot.

## 5. UI та recovery states

Admin `/inventory` отримує третій розділ «Постачальники» з:

- loading, empty, search/filter, error/retry;
- create/edit/deactivate/reactivate;
- field validation, duplicate і optimistic-conflict recovery;
- unsaved-close guard та responsive layout;
- active-only supplier picker у формі надходження.

Проведені operations, movements і lot snapshots лишаються незмінними.

## 6. Доказ

- migration на existing legacy lots;
- model/API/RBAC/audit/rollback та receipt integration tests;
- OpenAPI snapshot і generated TypeScript schema;
- frontend component tests, lint, strict typecheck, build та responsive browser gate.
