# Поточний checkpoint розробки

Дата: 2026-07-21

## Зафіксований стан

- TP-201—TP-207 і TP-301—TP-303 завершені; етапи auth/RBAC/довідників та пацієнтів/внутрішніх справ закрито, наступний послідовний пакет — TP-401.
- Реалізовані session auth/RBAC, password lifecycle, команда працівників, append-only audit, профіль клініки, приватний логотип, кабінети, каталог послуг, вісім системних статусів і clinic-wide графік із перервами.
- OpenAPI snapshot і TypeScript API schema оновлені разом із backend/frontend реалізацією.
- TP-301 реалізує normalized/indexed non-unique phone, стабільний public patient number, cursor pagination, live search, role-scoped selector, duplicate warning, atomic patient-create audit і responsive create/list UI.
- TP-302 реалізує one-to-one medical profile, role-specific `GET/PATCH /patients/{id}` projections, selector-level foreign-patient IDOR, atomic row-locked patient edit audit і responsive overview/history/photo shells. Reception payload не має medical/photo keys; реальні visit/photo/recommendation дані лишаються TP-601—605.
- TP-303 реалізує `GET/POST /work-items`, versioned `PATCH /work-items/{id}`, own/all role scope, safe patient link, active assignee та podologist/patient relationship validation, importance/due time й explicit complete/reopen. Create/update/complete/reopen атомарно пишуть audit; callback із картки пацієнта лише створює справу і не запускає дзвінок.
- Browser evidence для TP-203—TP-206 і TP-301—TP-303 збережені в `docs/evidence/`; TP-303 live check підтвердив desktop list/empty state, tablet create form, mobile locked callback context і відсутність console errors на `1440×900`, `768×1024`, `390×844`.
- Кореневий `AGENTS.md` вимагає окремо діагностувати й відновлювати несправні локальні компоненти замість повторення того самого невдалого виклику.

## Локальне середовище

- Docker Compose stack відновлений і readiness endpoint повертає `200`.
- Завислий orphan-контейнер `podoria-crm-backend-stuck` видалений; робочий контейнер `podoria-crm-backend-1` healthy.
- Вбудований браузер перевірений на `http://127.0.0.1:8088/settings`.
- Локальні credentials тестового адміністратора зберігаються лише в проігнорованому `.env.local`; `README.md` містить команду відтворення без відкритого пароля, а `.env.example` — безпечні placeholders.
- TP-206 gate: 93 backend tests і 33 frontend tests, Ruff, mypy, Django checks/migrations, lint, typecheck, contracts/OpenAPI і production build пройшли. Одноразовий `frontend-test` process segfault після lint окремо діагностовано; свіжий мінімальний typecheck і повний container check стабільно пройшли.
- Під час пізнішого повтору combined gate Docker Desktop не отримав exit event від точного `frontend-test` контейнера й не зміг його зупинити. Docker Desktop точково перезапущено; завислий контейнер зник, Compose stack знову healthy, readiness і `/settings` повертають `200`, а новий одноразовий frontend-контейнер виконав typecheck і був автоматично видалений. Stale test containers не лишилися.
- На початку TP-301 Docker API знову перестав відповідати під час першого backend check. Перевірено host processes і Docker logs, завислі клієнти зупинено, Docker Desktop перезапущено. Старий stateless backend-контейнер мав точний OCI blocker `container's cgroup is not empty`; його mounts перевірено, відтворено лише backend-контейнер без БД/volume змін. Після code-level admin typing fix stack, migrations і readiness відновлені.
- TP-301 gate: 110 backend tests і 40 frontend tests, Ruff/format, mypy, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, typecheck, 8 axe routes і production build пройшли. Host `npm run check` очікувано не має container-only `frontend/openapi/schema.json`; canonical fresh `frontend-test` gate із copied backend snapshot пройшов повністю.
- TP-302 gate: 120 backend tests і 46 frontend tests, Ruff/format, mypy для 74 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 9 axe routes, canonical fresh `frontend-test` і production web build пройшли.
- TP-303 gate: 129 backend tests і 53 frontend tests, Ruff/format, mypy для 86 source files, Django checks/migrations, OpenAPI snapshot, generated client, contracts, lint, strict typecheck, 10 axe routes, canonical `frontend-tools` check і production web build пройшли. Host `npm run check` очікувано не бачить container-only `frontend/openapi/schema.json`; призначений Compose tools gate підтвердив контракт без дублювання snapshot.
- Під час TP-302 Docker Desktop не отримав exit event старого backend-контейнера, а пізніше BuildKit лишив дві runtime-сесії з `0/0` steps. Обидва збої діагностовано окремо: зупинено лише підтверджені orphan CLI-процеси, видалено точні running build refs, Docker Desktop/BuildKit перезапущено, stack повернуто через `up -d --no-build`. Після відновлення одинарна runtime-збірка стабільно пройшла, `web` і backend healthy, readiness та `/patients` повертають `200`.

Browser adapter має точкове локальне виправлення у встановленому plugin cache для сумісності із захищеним `process` рантайму та вимкнення несправної ambient telemetry у browser runtime. Це виправлення лежить поза репозиторієм і може бути перезаписане під час оновлення плагіна; у такому разі потрібно окремо відновити компонент за правилом з `AGENTS.md`.

Під час TP-206 вбудований browser коректно виконав login, DOM interactions і responsive bounding-box checks. Його PNG compositor після повторних viewport override повертав stale/cropped tiles навіть після reload/new tab/full-page capture; фінальні screenshots тому відтворено `frontend/scripts/tp206-browser-check.mjs` у локальному Edge. Невалідний проміжний screenshot видалено. TP-301 повторно перевірено вбудованим browser без compositor blocker: create, live search, empty, duplicate/non-blocking create, unsaved guard і точні 1440×900, 768×1024, 390×844 layouts. TP-302 перевірено тим самим browser adapter: directory→card, medical edit із CSRF, server success, overview/history shells, responsive no-overflow і unsaved close guard. TP-303 перевірено без mutation тестових даних: work-items list/create і patient callback dialog на трьох viewport; viewport скинуто, вкладку закрито.

## Наступний пакет

Наступна запланована робота — TP-401: day/week calendar та free-slot query з clinic-wide working hours/breaks, specialist/room occupancy і role scope.
