# TP-303 — internal work items evidence

Дата перевірки: 2026-07-21.

## Responsive browser evidence

| Viewport | Артефакт | Перевірено |
|---|---|---|
| Desktop `1440×900` | `work-items-all-1440x900.png` | Role-aware navigation, summary, own/all та status controls, empty state і create CTA |
| Tablet `768×1024` | `work-items-create-768x1024.png` | Two-column create form, active assignee picker, type/due/patient/comment/importance fields |
| Phone `390×844` | `patient-callback-390x844.png` | Mobile sheet, preselected callback type, locked patient context і default assignee/title |

Live browser flow відкрив `/work-items`, create dialog і картку Марії Бондар → «Перетелефонувати». Callback form відобразила пацієнта як locked context і не виконувала mutation або автоматичний дзвінок. Console errors відсутні; тимчасові viewport override скинуто, тестову вкладку закрито.

## Automated proof

- `backend/tests/work_items/test_work_items_api.py`: callback/patient invariant, inactive assignee, podologist patient/task IDOR, own/all normalization, safe projection, version conflict, explicit complete/reopen, completed edit guard, missing version і authentication.
- `backend/apps/work_items/services.py`: row-locked versioned update, active assignee та patient relationship validation, same-transaction create/update/complete/reopen audit.
- OpenAPI snapshot і `frontend/src/api/schema.d.ts` фіксують typed list/create/PATCH operations та safe nested assignee/patient projections.
- `frontend/src/App.test.tsx`: role scope, all-team query, create з `X-CSRFToken`, completion із version і callback із locked patient.
- Canonical backend gate: 129 tests; Ruff/format, mypy (86 source files), Django checks і migration drift — green.
- Canonical frontend gate: 53 tests, з них 10 axe routes; contracts, ESLint, strict TypeScript і production build — green.

## Deferred scope

TP-303 не здійснює автоматичних дзвінків і не надсилає повідомлень. Appointment confirmation linkage, notification delivery та scheduling relationships підключаються у наступних calendar/notification packets.
