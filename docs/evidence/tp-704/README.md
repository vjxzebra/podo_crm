# TP-704: закриття, звірка та історія касових змін — evidence

Дата перевірки: 2026-07-22.

Статус: `done`. Implementation, automated, migration, runtime та authenticated
read-only browser gates пройшли; AC-16—AC-17 мають стан `verified`.

## Покритий scope

TP-704 додає authoritative close preview, versioned та idempotent
`POST /api/v1/cash-shifts/{id}/close`, role-scoped history
`GET /api/v1/cash-shifts`, immutable detail `GET /api/v1/cash-shifts/{id}` і
responsive `/finance/shifts`. Reception працює лише зі своїми shifts, admin —
з усіма, podologist не має доступу. Expected cash і discrepancy обчислює
сервер із append-only ledger; non-zero discrepancy потребує comment, CLOSED
shift не можна reopen/edit/delete і до неї не можна додати operation.

## Automated, contracts і build gates

- canonical `scripts/run-tests.ps1`: 298/298 backend tests;
- canonical frontend suite: 164/164 tests, зокрема 35/35 axe scenarios;
- focused billing suite: 71 tests;
- focused TP-704 API та migration coverage: 14 tests;
- close/history component і flow tests покривають zero actual, discrepancy,
  stale preview, exact retry, own/admin history, cursor/detail і mobile cards;
- OpenAPI JSON snapshot та generated TypeScript API schema синхронні;
- lint, strict typecheck і production frontend build пройшли.

Backend coverage містить balanced/excess/shortage close, strict request,
owner/admin/foreign reception/podologist RBAC, exact replay і payload mismatch,
double/concurrent close, close-vs-payment/refund/cash-adjustment races, audit
rollback, immutable snapshots, list filters/cursor та повний detail. Raw-SQL і
migration tests перевіряють lifecycle/formula/comment/closed-insert guards.

## Migration і збереження dev data

Dev migration smoke пройшов послідовність
`billing 0004 → 0005 → 0004 → 0005`; фінальний стан — `0005` applied. На кожній
межі звірено незмінність фінансових фактів. Після gate збережено:

- 1 OPEN shift `CSH-089CE5E936FC`;
- 1 CARD payment `TXN-337279B7D390` на `390050` minor units;
- payments/refunds/cash adjustments/ledger entries: `1/0/0/1`;
- opener і ledger actor snapshots backfilled;
- жодної CLOSED shift або reconciliation mutation не створено.

## Runtime gate

Production-like local runtime після фінальної migration відповідає `200`:

- `/`;
- `/finance`;
- `/finance/shifts`;
- `/health/ready`.

## Authenticated read-only browser gate

In-app Browser відкрив локальну CRM під admin session. Початковий stale tab
handle було точково відновлено очищенням лише невалідного binding та створенням
зареєстрованої вкладки; перезапуск Codex, Browser або dev-контейнерів не
знадобився.

Перевірено без фінансового submit:

- default desktop `/finance`: OPEN `CSH-089CE5E936FC`, revenue/card
  `3 900,50 грн`, expected cash `0,00 грн` і один append-only ledger row
  `TXN-337279B7D390` відображаються з immutable actor snapshot;
- close dialog стартує з порожнім actual cash; `0` є валідним значенням,
  показує «Каса зійшлася», counted confirmation активує final action. Після
  цього натиснуто лише `Скасувати`; `POST .../close` не виконувався;
- desktop `/finance/shifts` показує role-scoped history controls і OPEN row;
  detail містить повний ledger-derived summary та єдиний CARD entry;
- `768×1024` і `390×844` перемикаються на responsive cards без page-level
  horizontal overflow; серед видимих TP-704 controls немає цілей менших за
  `44×44 px`;
- browser console: `0` warnings/errors. Після viewport audit override скинуто,
  а тестову вкладку закрито.

Artifacts:

- [close dialog, ready but not submitted](01-close-dialog-ready-not-submitted.png);
- [desktop shift history](02-shift-history.png);
- [shift detail summary](03-shift-detail-ledger.png);
- [complete ledger row](04-shift-detail-entries.png);
- [mobile history filters](05-mobile-shift-history.png);
- [mobile shift card](06-mobile-shift-card.png).

Після browser gate повторний DB snapshot підтвердив той самий OPEN shift,
`closed_at/reconciliation/closed_by = NULL`, 1 CARD payment/ledger row та
counts `1/0/0/1`. Live close user-owned shift не виконувався.

## Наступна межа

TP-704 завершено, AC-16—AC-17 verified, GAP-02 resolved. Наступний пакет за
канонічним backlog — TP-801. Export, reopen/edit/delete CLOSED shift і
accounting reports до TP-704 не входять.
