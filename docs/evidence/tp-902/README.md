# TP-902 security/privacy hardening evidence

Дата: 2026-07-22. Контракт: [TP-902 security/privacy hardening](../../architecture/tp-902-security-privacy-hardening.md).

## Реалізований gate

- Login використовує fixed-window Redis counters: 5 invalid attempts на normalized-email
  digest і 30 на trusted-proxy client IP за 15 хвилин. Attempt резервується атомарно до
  password verification; blocked request повертає generic `429` + `Retry-After`, а
  успішний login прибирає зарезервований attempt.
- Server session має 30-хвилинний idle та 12-годинний absolute timeout. Expiry flush-ить
  session і повертає `401 session_expired`; frontend одразу unmount-ить protected shell та
  показує нейтральний login notice.
- Production defaults вимагають non-development `DJANGO_SECRET_KEY`, Secure cookies,
  HTTPS redirect, HSTS, `DENY`, `nosniff`, same-origin referrer/COOP. Proxy та direct API
  віддають CSP/Permissions-Policy, protected API — `Cache-Control: no-store`.
- Clinic logo тепер, як і visit photo, повністю декодується, перевіряє MIME/format,
  size/dimensions/decompression bomb і перекодовується без EXIF/metadata. Private reads,
  selector/serializer scope та IDOR negative cases повторно пройшли regression suite.
- Audit snapshots і JSON formatter редагують password/token/secret/cookie/signed URL/
  Authorization values; API exception envelope не повертає exception text.

## Automated gates

- canonical backend: `352 passed`; Ruff для 236 files, mypy для 182 source files,
  Django system check, fresh PostgreSQL migration cycle, OpenAPI validation/snapshot;
- canonical frontend: `198 passed` у 13 files; ESLint, strict TypeScript, generated client
  і Vite production build;
- component accessibility: `40` axe scenarios, включно з expired-session login state;
- migration-free check: `makemigrations --check --dry-run` — no changes;
  `migrate --plan` — no planned operations;
- `npm audit --omit=dev --audit-level=high` — `0 vulnerabilities`;
  `pip-audit` для `backend/requirements/base.txt` — `No known vulnerabilities found`;
- production `manage.py check --deploy`: `0` errors/critical warnings. Єдина advisory
  `security.W021` прийнята: HSTS preload навмисно лишається `False` до domain/rollback
  rehearsal у TP-903; HSTS one-year + subdomains уже ввімкнено.

## Live runtime/browser gate

- runtime `web`, `backend`, `proxy`, PostgreSQL і Redis healthy; `/` → `200`, readiness →
  `200`, unauthenticated `/api/v1/session` → `401`;
- root та API мають по одному CSP header; API має `no-store`, `DENY`, `nosniff`,
  same-origin referrer/COOP і Permissions-Policy;
- authenticated in-app Edge session була server-side переведена за idle deadline. Після
  reload URL став `/login`, protected shell count — `0`, session notice count — `1`,
  overflow — `false`, console warning/error — `0`;
- invalid unknown-account login показав тільки «Неправильний email або пароль.» й прибрав
  expiry notice, не розкривши account state;
- sanitized screenshot: [expired-session-login.png](expired-session-login.png). Перед
  записом email/password inputs програмно підтверджені як порожні; local email/password,
  cookie, token і signed URL у evidence відсутні;
- browser gate змінив лише ephemeral auth sessions/rate counters. 127 навмисно expired
  local admin sessions видалено, два exact login counters очищено; domain records не
  змінювались.

Machine-readable summary: [security-gate.json](security-gate.json).

## Build/runtime recovery

Перший web-build client був перерваний через занадто короткий shell timeout, але isolated
BuildKit builder лишився healthy і завершив ту саму збірку. Фінальний завантажений image
точно збігається з image запущеного `podoria-crm-web-1`. Після backend
recreate proxy один раз повернув startup `502`; logs показали normal migration/check
startup, після чого backend/proxy/web стали healthy та readiness стабільно повернув `200`.
Один двопотоковий Vitest verification-run втратив worker на `App.test.tsx`; файл окремо
пройшов `90/90`, а повний контрольований single-worker run — `198/198`, після чого Vite
production build завершився успішно.
