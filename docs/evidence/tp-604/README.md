# TP-604 browser evidence

Дата: 2026-07-22

Production Compose stack перевірено у вбудованому браузері на синтетичному DRAFT visit з однією послугою та однією material lot line. Перевірка була read-only щодо finish mutation: рекомендацію і confirmation заповнено, але submit не відправлено; після gate точний fixture видалено.

## Результат

- default desktop viewport: відображено patient/appointment context, service snapshot, server-derived total `1 450,00 грн`, material count/factual quantity, photo counts, recommendation, checked payment handoff та disabled-before-confirmation finish;
- після explicit confirmation кнопка `Завершити й передати на оплату` стала активною;
- mobile `390×844`: finish summary і primary controls доступні, bottom navigation не перекриває поточний крок, page horizontal overflow `0`;
- browser console: `0` errors на desktop і mobile;
- browser gate не створив inventory operation, stock movement, receivable або follow-up appointment; exact visit/appointment/patient/specialist/service/room/material/lot fixture cleanup залишив `0` rows;
- тимчасовий viewport скинуто, вкладку закрито;
- після recreation backend/web proxy повертав `502` через stale upstream IP; nginx log показав `172.19.0.4`, тоді як Docker DNS уже повертав `172.19.0.5`. Точковий restart лише proxy відновив `/health/ready` до `200`.

## Артефакти

- `finish-desktop.png` — desktop finish summary з рекомендацією та payment handoff;
- `finish-mobile.png` — mobile viewport finish summary без page overflow.

Canonical automated gate: `scripts/run-tests.ps1` — 218 backend tests, 106 frontend tests, 23 axe scenarios, OpenAPI/client snapshot, Ruff, mypy, Django checks/migrations from scratch, contracts, lint, strict typecheck і production build.
