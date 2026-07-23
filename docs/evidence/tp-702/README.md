# TP-702: finance operations і full-payment evidence

Дата перевірки: 2026-07-22.

## Покритий scope

TP-702 додає paid+unpaid finance projection з одним стабільним рядком на
`Receivable`, idempotent повну оплату на server-derived amount у власну OPEN
cash shift, same-transaction audit та zero-total auto-settlement без
Payment/ledger. Partial/split payment і custom amount не входять до контракту.

## Browser evidence

Authenticated read-only browser gate пройдено на desktop, tablet і mobile:

- [finance operation detail — desktop](finance-operation-detail-desktop.png);
- [full-payment dialog — desktop](full-payment-dialog-desktop.png);
- [full-payment dialog — tablet](full-payment-dialog-tablet.png);
- [full-payment dialog — mobile](full-payment-dialog-mobile.png);
- [finance operations list — mobile](finance-operations-mobile.png);
- [paid operation and ledger-derived totals — desktop](finance-paid-operation-desktop.png);
- [immutable paid operation detail — desktop](finance-paid-operation-detail-desktop.png).

Перевірено unpaid operation detail, відкриття full-payment dialog, read-only
server-derived total, amount inputs `0`, payment methods `3`, body scroll lock,
focus return, відсутність horizontal page overflow і console warnings/errors.
Після окремого live UI submit з `http://localhost:8088/finance` read-only gate
також підтвердив paid projection, card totals, immutable detail і відсутність
payment/refund actions у проведеному записі.

Автоматизований browser gate працював на `http://127.0.0.1:8088/finance`, не
відправляв payment mutation і не створював finance fixtures. Окрему валідну
оплату з `localhost` збережено як зовнішню/user-owned дію, а не очищено як
fixture. Idempotency/concurrency та zero-settled behavior підтверджені
API/component tests.

## Backend, data та contracts

- focused billing suite: 50 tests;
- dev migration smoke: rollback→reapply;
- шість активних billing triggers, зокрема два взаємні deferred aggregate
  guards для Receivable↔Payment consistency;
- OpenAPI snapshot, generated TypeScript client/contracts і static checks чисті;
- production frontend build пройшов.

## Canonical і runtime gates

- 266 backend tests;
- 137 frontend tests, включно з 14 `FinancePage` tests;
- 32 axe scenarios;
- runtime `/`, `/finance` і `/health/ready` — `200`.

## Межа наступних пакетів

TP-703 лишається відповідальним за full refund і cash deposit/withdrawal;
TP-704 — за close/reconciliation та shift history. Browser evidence цього пакета
не є доказом виконаного submit, refund або close mutation.
