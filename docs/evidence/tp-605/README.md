# TP-605 browser evidence

Дата перевірки: 2026-07-22.

Перевірка виконана у production Docker Compose build на
`http://127.0.0.1:8088` через authenticated admin session. Тимчасовий fixture
містив 1 пацієнта, 2 completed visits, 6 private BEFORE/AFTER photos і 3
recommendations. Browser працював read-only щодо server state: текст для
unsaved-guard вводився лише локально, submit не виконувався.

## Screenshots

- [Історія візитів, desktop 1280×900](history-desktop.png)
- [Архів фото, desktop 1280×900](photo-archive-desktop.png)
- [Popup carousel, desktop 1280×900](photo-carousel-desktop.png)
- [Popup carousel, phone 390×844](photo-carousel-mobile.png)
- [Рекомендації, tablet 834×1000](recommendations-tablet.png)

## Результати

- History показала рівно 2 cards у deterministic reverse chronology; stable
  service/cost snapshot, clinical summary та photo/recommendation counts
  відповідали fixture.
- Photo archive показав 2 visit groups і 6 thumbnails, розділених на
  «До процедури» та «Після процедури».
- Desktop dialog мав `1180×856` у viewport `1280×900`; signed image успішно
  завантажилась із natural size `1200×900`. Next button, `ArrowLeft`, tabs і
  thumbnails оновлювали group, caption і live counter (`1 із 2` / `2 із 2`).
- Focus trap циклічно повертався між close button і останньою thumbnail; `Esc`
  закривав carousel, повертав фокус на origin thumbnail і відновлював body
  scroll. Під час відкритого dialog body мав scroll lock.
- На phone viewport `390×844` dialog займав весь client viewport `375×844`;
  `scrollWidth=clientWidth=375`, усі кнопки/tabs мали target не менше `44px`.
- Tablet viewport `834×1000` показав рівно 3 recommendation cards без page
  overflow. Dirty create editor блокував `Esc` і Browser Back, Continue
  повертав фокус у textbox, Discard закривав форму без API mutation. Наступний
  Forward лишав той самий закритий recommendations route.
- Console warnings/errors: `0`. Viewport override скинуто, browser tab закрито.

## Cleanup

Після evidence capture видалено лише exact synthetic fixture: patient,
пов’язаний callback work item, 2 appointments, 2 visits, 6 photo rows, 3
recommendations, temporary service/room/podologist та 12 точних MinIO objects.
Повторна перевірка exact IDs, marker-залежностей, audit, inventory, billing і
`evidence/tp605/` object-key rows повернула `0` для всіх 26 checks.

Canonical gate: 226 backend tests, 117 frontend tests, Ruff/format для 177
Python files, mypy для 140 source files, clean migrations, OpenAPI/generated
client/contracts, lint, strict typecheck, production build і 28 axe scenarios.
