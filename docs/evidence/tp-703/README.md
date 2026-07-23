# TP-703: full refund і cash movements evidence

Дата перевірки: 2026-07-22.

## Покритий scope

TP-703 додає одне повне server-derived повернення зі способом початкової
оплати, окремі immutable `REFUND` operations і strict cash movements
`DEPOSIT`/`WITHDRAWAL` без пацієнта та способу оплати. Усі mutations потребують
власну поточну OPEN-зміну, idempotency key і атомарний audit; cash refund та
withdrawal повторно перевіряють доступну готівку під lock.

## Browser evidence

Authenticated read-only browser gate пройдено на desktop, tablet і mobile:

- [finance operations — desktop](finance-operations-desktop.png);
- [payment detail із refund action — desktop](payment-detail-refund-action-desktop.png);
- [full-refund dialog — desktop](full-refund-dialog-desktop.png);
- [cash-withdrawal dialog — desktop](cash-withdrawal-dialog-desktop.png);
- [finance operations — tablet](finance-operations-tablet.png);
- [cash-withdrawal dialog — mobile](cash-withdrawal-dialog-mobile.png).

Перевірено refundable payment picker, повну read-only суму `3 900,50 грн`,
успадкований read-only спосіб `Картка`, required reason і disabled confirmation
до валідного вводу. Withdrawal form містить лише суму, причину й optional
коментар, показує доступну готівку та не містить patient/payment-method
controls. На tablet широка operation table має власний horizontal scroll
(`overflow-x: auto`, `clientWidth=885`, `scrollWidth=1110`) без page overflow.
На mobile dialog займає весь client viewport `375×844`, body scroll
заблоковано, а `document.scrollWidth=clientWidth=375`. Console warnings/errors
відсутні.

Browser gate не вводив mutation payload і не натискав фінальне підтвердження,
тому не створив refund, deposit або withdrawal. Наявна user-owned CARD-оплата
`TXN-337279B7D390` не змінювалась і не видалялась.

## Backend, data та contracts

- focused billing suite: 57 tests;
- focused TP-703 API suite: 18 tests;
- `FinancePage`: 25 component tests;
- migration smoke: forward → reverse → forward;
- 13 активних billing triggers для lifecycle, append-only, typed-extension і
  reciprocal ledger invariants;
- dev DB після gate: 1 payment, 0 refunds, 0 cash adjustments, 1 ledger entry;
- OpenAPI `oneOf`/discriminator для `PAYMENT|REFUND|DEPOSIT|WITHDRAWAL`, strict
  request schemas і generated TypeScript client синхронні;
- Ruff, mypy, Django checks/migrations, lint, typecheck, contracts і production
  frontend build пройшли.

## Canonical і runtime gates

- 284 backend tests;
- 151 frontend tests;
- 35 axe scenarios;
- runtime `/`, `/finance` і `/health/ready` — `200`.

Після production recreation proxy один раз утримував старі upstream IP.
Перезапуск лише `proxy` відновив усі три `200`; БД, volumes і user-owned оплату
не змінювали.

## Межа наступного пакета

Закриття/reconciliation власної касової зміни та історія змін лишаються TP-704.
Partial refund, кілька refunds, custom method/amount і reversal не входять до
TP-703.
