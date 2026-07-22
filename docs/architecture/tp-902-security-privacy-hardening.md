# TP-902 — security and privacy hardening gate

Статус: frozen 2026-07-22. Packet не додає product features, external SSO або нові
business-domain contracts.

## 1. Межі

TP-902 повторно перевіряє завершені модулі як одну security boundary і закриває:

- brute-force protection для login без user enumeration;
- idle та absolute expiry server session;
- cookie, CSRF, transport і browser security headers;
- selector-before-serializer, object scope та indistinguishable `404` для IDOR;
- private logo/visit-photo content, upload type/size/decode/dimension/metadata validation;
- redaction паролів, token, cookie, signed URL та credentials в audit/log output;
- safe frontend recovery після `401`, `403`, `404` без залишення protected UI у DOM.

Зовнішній SSO, WAF, SIEM, provider-specific edge configuration, penetration test
стороннім постачальником і product permissions editor не входять у packet.

## 2. Authentication contract

### 2.1 Login rate limit

- invalid login однаково повертає `401 invalid_credentials` для unknown, inactive і
  wrong-password account;
- до password verification перевіряються два fixed-window counters у Redis: normalized
  email та client IP;
- default window — 15 хвилин, не більше 5 invalid attempts на email і 30 на IP;
- blocked request повертає generic `429 login_rate_limited` і `Retry-After`, не виконує
  password verification та не повідомляє, який counter спрацював;
- email у cache key зберігається лише як keyed digest; password/request body не
  журналюються;
- успішний login очищає email counter, але не чужі IP failures.

### 2.2 Session lifetime

- idle timeout за замовчуванням — 30 хвилин;
- absolute timeout за замовчуванням — 12 годин від login незалежно від activity;
- server session містить internal issued/last-seen timestamps, а cookie живе не довше
  absolute timeout;
- expired authenticated request атомарно flush-ить session і повертає
  `401 session_expired` з `WWW-Authenticate: Session`;
- active API request оновлює last-seen, але не absolute deadline;
- password change, temporary-password reset, deactivation і role change зберігають
  уже наявну revocation поведінку.

## 3. Browser and transport boundary

- session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` поза explicit local override;
- CSRF cookie та unsafe API mutations зберігають Django CSRF validation;
- production defaults: HTTPS redirect, trusted proxy scheme, HSTS один рік із
  subdomains, `nosniff`, `DENY` framing та `same-origin` referrer policy;
- proxy і direct backend responses мають CSP, Permissions-Policy та інші однакові
  browser headers; protected API responses мають `Cache-Control: no-store`;
- CSP забороняє third-party script/style/frame/object і дозволяє лише погоджені image
  sources для private object storage.

## 4. Privacy and object scope

- кожен object endpoint застосовує role/object selector до serialization; foreign або
  invisible object не відрізняється від absent object (`404`);
- reception payload фізично не містить medical/photo/recommendation keys;
- global search і notifications не повертають forbidden category/object/deep link;
- private content read потребує authenticated signed purpose/expiry та повторної
  role/object перевірки;
- logo та visit photo відхиляють MIME spoofing, malformed/decompression-bomb content,
  oversize/dimension excess; accepted raster декодується й перекодовується без EXIF/GPS;
- audit snapshots і JSON logs замінюють sensitive values на `[REDACTED]`; API `500`
  ніколи не повертає exception text або stack trace.

## 5. Frontend expiry behavior

- будь-який `401` від protected API переводить auth boundary в anonymous state;
- protected routes, dialogs, cached component state і patient/finance/medical data
  одразу unmount-яться;
- login page показує нейтральне повідомлення про завершену session, не називає account
  status і не відновлює unsafe dynamic deep link автоматично;
- invalid login `401` не маскується під expired session;
- `403` показує role-safe forbidden state/redirect, `404` — generic not-found без
  підтвердження існування object; network failure лишається retryable і не підміняється
  logout.

## 6. Exit criteria

- focused auth/session/headers/upload/redaction/IDOR/frontend-expiry suites green;
- canonical backend/frontend/OpenAPI/migration gates green;
- production settings pass Django deploy checks без critical warning;
- authenticated browser journey підтверджує live expiry → login notice → protected DOM
  removed; invalid credentials лишаються generic;
- dependency/security scan не має known critical/high findings або містить documented
  explicit exception із owner і строком;
- tracked artifacts не містять local credentials, raw session/token або signed URLs.
