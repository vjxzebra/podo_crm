# TP-404 evidence — calendar responsive/concurrent rendering gate

Дата перевірки: 2026-07-21.

## Реалізований gate

- Day/week scrollers мають доступні назви, видиму інструкцію для horizontal scroll, `tabIndex=0`, focus-visible state й контрольований внутрішній overflow без page overflow.
- На tablet/mobile 15-хвилинні вільні слоти, toolbar controls і основна calendar CTA мають мінімальну висоту `44px`; sticky header і обмежена висота сітки лишають horizontal scrollbar досяжним.
- Дві одночасні події мають однаковий start row, різні specialist columns, `0` геометричних перетинів і не мають text clipping.
- Detail dialog отримує focus на close control і після закриття повертає його на event card, що відкрила dialog. Week cards мають однозначні accessible names.

## Автоматичні перевірки

- Canonical `scripts/run-tests.ps1`: 153 backend tests і 70 frontend tests успішні, з них 13 axe scenarios.
- Ruff format/check для 125 Python files, mypy для 98 source files, Django checks/migration drift, OpenAPI snapshot/generated TypeScript schema, frontend contracts/lint/strict typecheck і production build успішні.
- `frontend/scripts/tp404-browser-check.mjs` виконує read-only native Edge gate з credentials лише з локального `.env.local`: точні viewport, page/internal overflow, bounding boxes, clipping, `ArrowRight`, native `Enter`, dialog focus-return і console/page errors.

## Live browser evidence

| Viewport / стан | Файл | Перевірені метрики |
|---|---|---|
| Desktop `1440×900` day | [calendar-desktop-1440x900.png](calendar-desktop-1440x900.png) | page `1440/1440`; 2 events, 0 overlaps, no clipping; усі 5 columns вмістилися |
| Tablet `768×1024` day | [calendar-tablet-768x1024.png](calendar-tablet-768x1024.png) | page `768/768`; scroller `644/1114`; slots/controls `44px`; обидві concurrent cards видимі |
| Mobile `390×844` day | [calendar-mobile-390x844.png](calendar-mobile-390x844.png) | page `390/390`; scroller `390/1114`; slots/controls `44px`; mobile navigation доступна |
| Mobile `390×844` week | [calendar-week-mobile-390x844.png](calendar-week-mobile-390x844.png) | page `390/390`; week scroller `390/1470`; 7 days і 2 events |

Native keyboard gate змінив day scroller `scrollLeft` з `0` на `40` на tablet/mobile. `Enter` відкрив event detail, close control отримав focus, а після закриття active accessible name знову був `10:00 Марія Бондар, Підтверджено`. Browser console/page errors: `[]`; business mutations не виконувалися.

In-app browser успішно перевірив authenticated DOM, touch sizes, day/week ARIA semantics і dialog focus lifecycle. Його compositor після viewport override повертав stale/cropped tiles навіть після fresh tab і reload; точні PNG тому створені відтворюваним Edge harness, а три невалідні проміжні JPEG видалені. Тимчасовий viewport override скинуто після перевірки.
