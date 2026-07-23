# TP-201 session auth and RBAC evidence

Перевірено 2026-07-20 через production Docker build і Microsoft Edge з точними CSS viewport. Вбудований browser connector був недоступний через bootstrap error середовища, тому той самий локальний critical path виконано відтворюваним fallback-скриптом `frontend/scripts/tp201-browser-check.mjs`.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Anonymous direct URL → login | 1440×900 | `/inventory` без сесії відкриває production login без role switcher | [login-desktop-1440x900.png](login-desktop-1440x900.png) |
| Reception direct URL guard | 1440×900 | Після серверного login `/inventory` безпечно перенаправляє на огляд; склад/аналітика/settings відсутні в меню | [reception-direct-url-1440x900.png](reception-direct-url-1440x900.png) |
| Admin mobile navigation | 390×844 | Серверний admin scope відображає всі дозволені модулі у mobile sheet | [admin-mobile-menu-390x844.png](admin-mobile-menu-390x844.png) |

Автоматизовані докази:

- backend: 31 test загалом, з них 20 нових auth/RBAC tests; перевірено три ролі, generic invalid-credentials response, inactive user, CSRF, session-key rotation, logout flush, 401, case-insensitive email uniqueness і централізовані permission classes;
- frontend: 11 session/route/component tests і 5 axe-core checks; перевірено login error/success, logout, reception direct-URL redirect і приховану недоступну навігацію;
- OpenAPI snapshot і generated TypeScript client містять `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/session` та cookie auth scheme;
- live Edge check: `{"login":"ok","directUrl":"ok","logout":"ok","mobileAdmin":"ok"}`.

Session cookie має окреме ім’я, `HttpOnly` і `SameSite=Lax`; `Secure` увімкнений за замовчуванням поза `DEBUG`. Login явно захищений CSRF, а CSRF cookie окремий і доступний клієнту для `X-CSRFToken`.
