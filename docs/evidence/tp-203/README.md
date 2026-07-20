# TP-203 team lifecycle evidence

Перевірено 2026-07-21 через production Docker build і Microsoft Edge `150.0.4078.83` з точними CSS viewport. Вбудований browser connector був недоступний через bootstrap conflict середовища, тому critical path виконано відтворюваним fallback-скриптом `frontend/scripts/tp203-browser-check.mjs`.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Admin team list/search/status | 1440×900 | Реальні server users, fixed role/status projections, last activity й row actions; inactive profile збережений у списку | [team-list-1440x900.png](team-list-1440x900.png) |
| Create form і role access summary | 768×1024 | Повний §12.2 contract; зміна ролі на reception оновлює короткий перелік доступів; password/active/first-login controls окремі | [team-create-role-access-768x1024.png](team-create-role-access-768x1024.png) |
| Responsive team cards | 390×844 | Table переходить у touch-friendly cards без горизонтального overflow; основні дії й status facts доступні | [team-cards-390x844.png](team-cards-390x844.png) |

Автоматизовані докази:

- backend: 57 tests загалом; TP-203 додає 9 tests для search/filter/detail, create/password policy, case-insensitive email, edit/role change, session revocation, deactivate/reactivate, RBAC і audit;
- PostgreSQL concurrency: дві одночасні demotion двох active admins дають рівно один success і один `last_admin_protected`, після commit лишається один active admin;
- frontend: 24 tests, з них 6 axe-core routes; TP-203 покриває create/role summary, server `409` state, reception navigation/direct URL і axe для `/team`;
- OpenAPI snapshot і generated TypeScript client містять `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/deactivate` та окремий existing temporary-password endpoint;
- live Edge check: `{"adminTeamList":"ok","createRoleAccess":"ok","mobileCards":"ok","receptionBoundary":"ok"}`.

Custom permissions, branches і видалення працівника не входять у TP-203. Деактивація зберігає historical foreign keys; email/SMS delivery тимчасового пароля відсутня за прийнятим TP-202 scope.
