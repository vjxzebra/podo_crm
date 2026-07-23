# TP-1001 — supplier directory

Статус: `done` 2026-07-23.

## Реалізований зріз

- Admin-only `Supplier` має case-insensitive unique name, контакти, active state,
  optimistic `version`, create/update/deactivate/reactivate audit і не має business
  delete API.
- `MaterialLot` отримав nullable protected FK, а `supplier_name` лишився immutable
  історичним snapshot. Migration `0007_supplier_directory` створює довідник з
  legacy назв і прив’язує партії без переписування snapshot.
- Receipt line приймає optional `supplier_id`, вимагає active supplier, серверно
  фіксує назву та перевіряє identity/snapshot під час поповнення наявної партії.
  Старий `supplier_name` contract лишився backward-compatible.
- `/inventory?section=suppliers` має loading/empty/error/retry, search/status,
  create/edit/deactivate/reactivate, field/conflict recovery та unsaved guard.
  Форма надходження завантажує лише active suppliers.

## Automated gates

- focused supplier backend: `23/23`;
- canonical backend: `372/372`;
- canonical frontend: `200/200` у 13 files, з них `40/40` accessibility scenarios;
- Ruff/format для 248 Python files, mypy для 189 source files, Django checks,
  `makemigrations --check`, OpenAPI validation/snapshot, generated TypeScript
  schema, contracts, ESLint, strict typecheck і production build — green;
- populated local migration зберегла legacy name і прив’язала `1/1` named lot.

Один unrelated `Ctrl/Cmd+K` test під час повторного image build не вклався у
timeout; точковий повтор пройшов, а наступний повний gate стабільно завершився
`200/200`. Фінальний production web image з mobile touch-target fix успішно
зібрано й запущено.

## Runtime та безпека

Під час виконання за правилом `AGENTS.md` точково відновлено bind-file permission
для OpenAPI snapshot, writable Ruff/mypy caches і Docker Desktop після завислого
test container. Жоден volume або domain record не видалявся; backend/web/proxy
healthy, `/health/ready` і `/inventory?section=suppliers` повертають `200`.

Browser DOM snapshot один раз показав значення локального password-поля. Старий
credential одразу ротовано в Git-ignored `.env.local` і локальному admin через
`provision_dev_user`; sessions відкликано, `.env.local` підтверджено ignored,
DB password match і повторний authenticated login пройшли. Нове значення ніде в
tracked evidence не збережено.

## Authenticated responsive browser evidence

In-app browser перевірив directory, search empty state, edit modal lifecycle та
active supplier picker у receipt без submit. Desktop, `768×1024` і `390×844` не
мають page overflow. Виявлені 36px section controls збільшено до 44px; повторний
tablet/mobile probe підтвердив по `44px` для всіх трьох перемикачів. Mobile modal
має ширину в межах viewport, body lock і close target `44×44`; browser console
не містить warnings або errors.

- [Desktop directory](supplier-directory-desktop.png)
- [Tablet directory](supplier-directory-tablet-768x1024.png)
- [Mobile directory](supplier-directory-mobile-390x844.png)
- [Desktop edit modal](supplier-edit-modal-desktop.png)
- [Mobile edit modal](supplier-edit-modal-mobile-390x844.png)
- [Receipt supplier picker](receipt-supplier-picker-desktop.png)
