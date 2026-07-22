# TP-603 browser evidence

Дата: 2026-07-22

Production Compose stack перевірено у вбудованому браузері на синтетичному DRAFT visit із одним BEFORE і одним AFTER JPEG. Фото та previews лежали у private MinIO й відкривалися тільки через authenticated signed content endpoint; після gate точний fixture і всі чотири object keys видалено.

## Результат

- desktop `1280×900`: два блоки по 444 px розміщені поруч, обидва previews завантажені (`480×360`), page overflow `0`;
- tablet `834×1000`: блоки по 652 px утворюють одну колонку, мінімальна висота photo controls `44px`, page overflow `0`;
- mobile `390×844`: блоки по 353 px утворюють одну колонку, мінімальна висота controls `44px`, page overflow `0`;
- DOM підтвердив окремі BEFORE/AFTER counts, upload controls, metadata, delete controls, privacy notice і disabled TP-604 CTA;
- thumbnail відкриває visit-wide modal slider; desktop `1280×720` повністю вміщує header, `1200×900` original, arrows і footer, а mobile `390×844` має page overflow `0` та controls не менші за `44px`;
- next button перемикає `1 із 2` → `2 із 2`, `ArrowLeft` повертає попереднє фото, `Esc` закриває popup, відновлює body scroll і повертає фокус на вихідний thumbnail;
- browser console: `0` warning/error;
- read-only gate не створив upload intent або photo write audit і не змінив visit version (`1`); fixture cleanup залишив `0` visit rows.

## Артефакти

- `desktop.png` — два приватні photo cards поруч;
- `tablet.png` — stacked BEFORE/AFTER layout;
- `mobile.png` — mobile BEFORE card, 44px controls і bottom navigation.
- `slider-desktop.png` — desktop popup із contained original, arrows, close і counter;
- `slider-mobile.png` — fullscreen mobile popup із contained original і 44px controls.

Canonical automated gate: `scripts/run-tests.ps1` — 208 backend tests, 103 frontend tests, 22 axe scenarios, OpenAPI/client snapshot, Ruff, mypy, Django checks/migrations, lint, typecheck і production build.
