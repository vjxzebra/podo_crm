# TP-601 — start visit та examination draft

Дата перевірки: 2026-07-21

## Реалізований зріз

- `POST /api/v1/appointments/{appointment_id}/start-visit` атомарно переводить лише `ARRIVED` appointment у `IN_PROGRESS` і створює не більше одного visit.
- Assigned podologist та admin мають object access; reception отримує `403`, foreign podologist — scoped `404`.
- Повторний start повертає наявний visit (`200`) без duplicate visit або audit; перший успішний виклик повертає `201`.
- `GET /api/v1/visits/{visit_id}` та versioned `PUT /api/v1/visits/{visit_id}` зберігають examination draft з complaint XOR, objective examination, фіксованими detected conditions і podologist notes.
- Start/draft не створюють stock movements, inventory operations, receivables/payments і не завершують visit.
- `/visits/{visit_id}` має чотирикрокову навігацію з активним examination step, autosave/manual save, validation/retry/optimistic-conflict та unsaved-exit states. Кроки 2–4 навмисно лишаються disabled до TP-602—604.

## Browser gate

Перевірка виконана у вбудованому браузері на локальному production Compose stack. Для read-only evidence були створені точні тимчасові fixtures з ARRIVED appointment і visit; UI не відправляв mutation. Після перевірки visit лишився з `version=1`, draft audit count дорівнював `0`, а всі fixtures були видалені.

| Viewport | Результат | Артефакт |
|---|---|---|
| Desktop `1280×720` | Authenticated visit header, appointment summary, 4-step navigation і populated examination form читабельні | [visit-examination-desktop.png](visit-examination-desktop.png) |
| Tablet `834×1000` | Summary та steps переходять у компактне компонування без page overflow | [visit-examination-tablet.png](visit-examination-tablet.png) |
| Mobile `390×844` | Page horizontal overflow `0`; ключові кнопки `44px`; step navigation має лише власний intentional horizontal scroll | [visit-examination-mobile.png](visit-examination-mobile.png) |

Console errors: `0`. Console warnings: `0`.

## Автоматизовані докази

- Backend: `backend/tests/visits/test_visit_start_and_draft.py` — 9 сценаріїв для transition/idempotency, RBAC/IDOR, validation/version conflict, audit rollback, concurrent start, no-side-effects і OpenAPI.
- Frontend: TP-601 scenarios у `frontend/src/App.test.tsx` — exact start/save contracts, invalid/unsaved behavior і reception visibility.
- Accessibility: direct visit workspace та unsaved dialog у `frontend/src/app/accessibility.test.tsx`.
- Canonical `scripts/run-tests.ps1`: 192 backend tests, 92 frontend tests, 20 axe scenarios, Ruff/format (153 Python files), mypy (120 source files), Django checks/migrations, OpenAPI/generated client/contracts, lint, strict typecheck і production Vite build — green.
