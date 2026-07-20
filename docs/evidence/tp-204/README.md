# TP-204 clinic settings evidence

Перевірено 2026-07-21 через production Docker build і Microsoft Edge `150.0.4078.83` з точними CSS viewport. Вбудований browser connector був недоступний через повторюваний bootstrap conflict середовища, тому critical path виконано відтворюваним fallback-скриптом `frontend/scripts/tp204-browser-check.mjs`.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Singleton clinic profile | 1440×900 | Повні name/phone/email/address/description поля, private logo control, one-location badge; branch/type controls відсутні | [clinic-profile-1440x900.png](clinic-profile-1440x900.png) |
| Room create state | 768×1024 | ADR-001 пояснення, active control, no-delete/history semantics і touch-friendly dialog | [room-create-768x1024.png](room-create-768x1024.png) |
| Responsive room catalog | 390×844 | Summary і room cards без горизонтального overflow; create/edit actions доступні над mobile navigation | [room-catalog-390x844.png](room-catalog-390x844.png) |

Автоматизовані докази:

- backend: 68 tests загалом; TP-204 додає 11 tests для singleton seed/constraint, full profile, validation, optimistic conflict, room lifecycle/case-insensitive conflict/no-delete, RBAC, private logo validation/read і audit;
- frontend: 28 tests, з них 7 axe-core routes; TP-204 покриває full profile save, room empty/create, duplicate/stale `409`, reception navigation/direct URL і axe для `/settings`;
- private object storage: реальний MinIO put/get/delete roundtrip пройшов через private bucket; logo API дозволяє лише PNG/JPEG до 5 МБ, перевіряє magic bytes і не повертає object key;
- OpenAPI snapshot і generated TypeScript client містять `GET/PATCH /clinic-profile`, `GET/PUT /clinic-profile/logo`, `GET/POST /rooms` і `PATCH /rooms/{id}`;
- live Edge check: `{"clinicProfile":"ok","roomCreateState":"ok","mobileRoomCatalog":"ok","receptionBoundary":"ok"}`.

Branches, room deletion і appointment occupancy constraint не входять у TP-204. `Room` зберігає stable UUID та active state; appointment FK, label snapshot і PostgreSQL exclusion constraint реалізуються в TP-401—402 за ADR-001.
