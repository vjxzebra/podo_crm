# TP-302 — patient card/edit evidence

Дата перевірки: 2026-07-21.

## Responsive browser evidence

| Viewport | Артефакт | Перевірено |
|---|---|---|
| Desktop `1440×900` | `patient-card-medical-1440x900.png` | Medical overview, header/contact facts, locked patient link до нового запису, visit shell; `rootScrollWidth == rootClientWidth` |
| Tablet `768×1024` | `patient-card-history-768x1024.png` | Compact rail, card actions/facts, history tab empty state; `rootScrollWidth == rootClientWidth` |
| Phone `390×844` | `patient-card-edit-unsaved-390x844.png` | Responsive medical edit fields, visible unsaved-change confirmation, mobile navigation; `rootScrollWidth == rootClientWidth` |

Live browser flow відкрив patient directory → картку Марії Бондар, виконав CSRF-protected PATCH і отримав server success «Зміни картки пацієнта збережено й зафіксовано в журналі дій». Після відповіді overview відобразив алергію «Латекс», хронічний стан «Цукровий діабет» і медичну нотатку. Тимчасовий viewport після перевірки скинуто, тестову вкладку закрито.

## Automated proof

- `backend/tests/patients/test_detail_and_edit.py`: admin medical projection, reception serialization absence, safe/medical edits, same-transaction before/after audit, forbidden reception medical PATCH, podologist foreign-patient GET/PATCH `404`, validation та profile creation.
- OpenAPI snapshot і `frontend/src/api/schema.d.ts` фіксують polymorphic reception/medical detail response та typed PATCH request.
- `frontend/src/App.test.tsx`: directory navigation, overview/history/photo shells, reception-safe UI without medical/photo content, typed PATCH із `X-CSRFToken`, unsaved guard і safe not-found state.
- Canonical backend gate: 120 tests; Ruff/format, mypy, Django checks і migration drift — green.
- Canonical frontend gate: 46 tests, з них 9 axe routes; contracts, ESLint, strict TypeScript і production build — green.

## Deferred scope

TP-302 навмисно постачає role-safe visit/photo metadata shells. Реальні appointments, completed visit history, private before/after photo lifecycle/carousel і recommendations реалізуються у TP-401—TP-605. Кнопка «Перетелефонувати» лишається disabled до TP-303.
