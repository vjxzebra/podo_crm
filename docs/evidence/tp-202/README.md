# TP-202 password lifecycle evidence

Перевірено 2026-07-21 через production Docker build і Microsoft Edge `150.0.4078.83` з точними CSS viewport. Вбудований browser connector був недоступний через bootstrap conflict середовища, тому critical path виконано відтворюваним fallback-скриптом `frontend/scripts/tp202-browser-check.mjs`.

| Critical path | Viewport | Результат | Evidence |
|---|---:|---|---|
| Enumeration-safe forgot request | 390×844 | Відомий і невідомий email мають однаковий generic success; modal не розкриває наявність account | [forgot-generic-success-390x844.png](forgot-generic-success-390x844.png) |
| Forced first login | 1440×900 | Тимчасова сесія має `route_ids=[]`; app shell не монтується, показана незакривна форма власного пароля | [first-login-block-1440x900.png](first-login-block-1440x900.png) |
| Admin reset queue/deep link | 1440×900 | Admin бачить pending request, працівника й окрему форму тимчасового пароля | [admin-reset-queue-1440x900.png](admin-reset-queue-1440x900.png) |
| Own password form | 768×1024 | Profile action відкриває окремий current/new/confirmation contract без admin-reset полів | [own-password-form-768x1024.png](own-password-form-768x1024.png) |

Автоматизовані докази:

- backend: 37 tests загалом; TP-202 додає 6 lifecycle tests для current-password guard, password policy/mismatch, forced/expired temporary password, enumeration-safe/deduplicated requests, admin-only queue, session rotation/revocation і resolved request;
- frontend: 16 application/component tests і 5 axe-core checks; покрито first-login block/success/expired state, forgot success, own change та admin temporary-password queue;
- OpenAPI snapshot і generated TypeScript client містять усі чотири AC-21 mutation endpoints і admin list endpoint;
- live Edge check: `{"forgotGeneric":"ok","firstLoginBlock":"ok","adminResetQueue":"ok","ownPasswordForm":"ok"}`.

Email/SMS delivery не входить у TP-202: після позасистемної перевірки працівника адміністратор передає тимчасовий пароль вручну. Browser harness не виконує фінальний submit зміни пароля; mutations повністю перевірені API/component tests.
