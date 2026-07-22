# TP-701 cash-shift evidence

Дата перевірки: 2026-07-22.

Перевірка виконана на production Docker Compose build за адресою
`http://127.0.0.1:8088` через authenticated local-admin session. UI не
створював і не змінював бізнес-дані: no-shift dialog закривався через `Esc`, а
populated state читав точний synthetic ledger fixture.

## Screenshots

- [Немає відкритої зміни, desktop 1440×900](no-shift-desktop-1440x900.png)
- [Підтвердження нульового залишку, desktop 1440×900](open-shift-dialog-desktop-1440x900.png)
- [Поточна зміна й ledger, desktop 1440×900](open-shift-desktop-1440x900.png)
- [Поточна зміна, tablet 768×1024](open-shift-tablet-768x1024.png)
- [Поточна зміна, phone 390×844](open-shift-mobile-390x844.png)

Відтворюваний browser gate: [tp701-browser-check.mjs](../../../frontend/scripts/tp701-browser-check.mjs).

## No-shift та dialog

- Сторінка показала рівно одну CTA `Відкрити касову зміну`; current-shift
  section була відсутня, horizontal page overflow дорівнював `0`.
- Confirmation dialog мав `590×302`, fixed opening balance `0,00 грн` і жодного
  `input`. Початковий фокус стояв на `Скасувати`, body мав scroll lock.
- `Esc` закрив dialog, повернув фокус на CTA та відновив body scroll. Submit не
  натискався, тому `cash.shift_opened` audit і shift row не створювалися.

## Ledger fixture та формули

Synthetic OPEN shift `CSH-701000000000` містив 8 append-only entries:

- payments: cash `1 000,00 грн`, card `2 500,00 грн`, transfer `1 500,00 грн`;
- refunds: cash `200,00 грн`, card `300,00 грн`, transfer `100,00 грн`;
- deposit `500,00 грн`, withdrawal `150,00 грн`.

UI точно відтворив ledger-derived totals: payments `5 000,00 грн`, refunds
`600,00 грн`, revenue `4 400,00 грн`, expected cash `1 150,00 грн`. Deposit і
withdrawal показали `Не застосовується`, а не готівковий спосіб. Journal мав
ARIA table/row/columnheader/cell semantics, рівно 8 rows у reverse chronology
та жодної payment/refund/deposit/withdrawal/close/history кнопки з майбутніх
TP-702—TP-704.

## Responsive gate

| Viewport | Summary columns | Ledger columns | Page overflow | Console warnings/errors |
|---|---:|---:|---:|---:|
| 1440×900 | 4 | 5 | 0 | 0 |
| 768×1024 | 2 | 2 | 0 | 0 |
| 390×844 | 1 | 1 | 0 | 0 |

Tablet і phone приховали desktop ledger header, але зберегли доступні labels
кожної комірки. На phone desktop sidebar була відсутня, mobile bottom nav
відображалась, current hero і ledger займали рівно client width.

In-app browser успішно виконав DOM interactions, focus checks і точні geometry
assertions. Його PNG compositor після viewport override потрапив у stale CDP
context і 125% Windows-DPI mismatch, через що правий край кадру обрізався. Після
діагностики canonical PNG та повторні незалежні assertions створено headless
Edge script; viewport override скинуто, обидві in-app tabs закрито.

## Backend та contract evidence

- `POST /api/v1/cash-shifts` не має request body або `Idempotency-Key` header;
  reception/admin відкривають лише власну зміну, podologist отримує `403`.
- Partial unique constraint і user-row lock блокують serial/concurrent duplicate
  open; named constraint мапиться у `409 cash_shift_already_open`.
- Shift create та `cash.shift_opened` audit commit-яться разом; fault-injected
  audit failure не залишає shift row.
- PostgreSQL triggers `billing_cash_shift_lifecycle` і
  `billing_cash_ledger_entry_append_only`, model/queryset guards та read-only
  admin блокують raw/ORM delete, identity mutation, reopen і ledger update.
- Forward→reverse→forward migration smoke пройшов; reverse прибрав обидва
  triggers, повторний forward їх відновив.
- OpenAPI snapshot і generated TypeScript client мають exact projection fields,
  integer user IDs, UUID shift/entry IDs та nullable `shift`/`payment_method`.

## Cleanup і gates

Перед cleanup перевірено exact shift ID, actor email, усі 8 exact entry IDs і
відсутність UI-created audit. Тригери вимкнено лише локально всередині однієї
транзакції, видалено рівно 8 fixture entries і 1 fixture shift. Після cleanup
`CashShift=0`, `CashLedgerEntry=0`, exact `cash.shift_opened` audit count `0`;
локального користувача не змінено.

Focused gate: 22 billing backend tests, 6 FinancePage component tests і 2
finance axe scenarios. Canonical `scripts/run-tests.ps1`: 248 backend tests,
127 frontend tests, 30 accessibility scenarios, Ruff/format для 185 Python
files, mypy для 145 source files, Django checks/clean migrations, OpenAPI і
generated client/contracts, lint, strict typecheck та production build.

Після точкового BuildKit/Compose recovery backend, web і proxy healthy,
worker/beat ready; `/health/ready` та `/finance` повертають `200`, а
unauthenticated `/api/v1/cash-shifts/current` — `401`.
