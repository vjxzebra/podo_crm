# TP-904 — release acceptance evidence

## Результат

TP-904 завершено 2026-07-23: усі `23/23` критерії приймання мають стан
`verified`. Фінальний gate поєднав канонічні тести, full-role browser UAT,
перевірку populated/fresh database, dependency та runtime-image audits,
production-like deployment rehearsal і повторне використання encrypted
restore/deploy/rollback доказів TP-903.

Machine-readable джерело істини — [acceptance-gate.json](acceptance-gate.json).
Його структура, evidence paths і точні release invariants перевіряються командою:

```powershell
.\scripts\release\verify-acceptance.ps1
```

## Канонічний quality gate

- backend: `364 passed`, Ruff/format — `246 files`, mypy — `188 source files`;
- frontend: `198 passed` у `13` test files, `40` component axe scenarios;
- Django checks, fresh migrations, OpenAPI snapshot/generated client і production
  build — green;
- повторні frontend runs пройшли у thread pool без зависання worker shutdown.

## Full-role browser UAT

Podologist, reception і admin перевірені на `1440×900`, `1024×768` і
`390×844`. Сукупний результат:

- `75` route checks;
- `11` forbidden direct-URL redirects;
- `0` serious/critical axe violations;
- `0` browser warnings/errors.

UAT був read-only щодо clinical, finance та inventory mutations. Їхні submit,
concurrency, idempotency, audit і rollback semantics повторно підтвердив
автоматизований suite. Після gate тимчасові UAT users, patients, appointments,
services, rooms, notifications і work items видалені; контрольні counts
`users/patients/appointments = 0/0/0`.

Докази:

- [combined browser gate](browser-gate.json);
- [admin gate](browser-gate-admin.json);
- [reception gate](browser-gate-reception.json);
- [podologist gate](browser-gate-podologist.json);
- representative screenshots: [admin overview](admin-overview-desktop.png),
  [admin inventory](admin-inventory-desktop.png),
  [reception finance](reception-finance-desktop.png),
  [reception phone](reception-overview-phone.png),
  [podologist calendar](podologist-calendar-desktop.png),
  [podologist phone](podologist-overview-phone.png).

## Database, dependencies та candidate images

- populated restore verification: `53` migrations, `10` object references,
  `0` missing objects, `0` pending migrations, `0` invalid constraints;
- `npm audit --omit=dev`: `0` known vulnerabilities;
- `pip-audit`: `43` dependencies, `0` known vulnerabilities;
- candidate backend, web і ops images: `0 critical/high` Docker Scout findings;
- backend candidate: `sha256:e221fce9f1c056b666a385844fa841d68dd78c560c5a91f08a821dd275d61f16`;
- web candidate: `sha256:4e278be7665a30f44cbdb379e926da3d1c03c1279a28fd1b480fca7b470cef91`.

Backend runtime переведено на Alpine/PostgreSQL-only Python runtime, а web/proxy
runtime — на patched Alpine nginx. Production overlay використовує той самий
immutable web candidate і для frontend, і для edge proxy.

## Production rehearsal та recovery

Ізольований Compose project розгорнув `8` services із file-mounted secrets та без
application source mounts. Recovery-manifest preflight і Django deploy check
пройшли; root/readiness/unauthenticated-session повернули `200/200/401`.
Після перевірки project, volumes, networks і тимчасова secret directory очищені —
усі cleanup counts дорівнюють нулю.

Encrypted PostgreSQL/MinIO restore, negative restore gates, immutable deployment і
image-only rollback без reverse migrations повторно валідуються за
[TP-903 operations gate](../tp-903/operations-gate.json).

Прийняті non-blocking advisories:

- `security.W008` очікуваний лише в локальній HTTP rehearsal без SSL redirect;
- `security.W021` відображає явне рішення не вмикати HSTS preload до enrollment
  production domain;
- Vite повідомляє про bundle понад advisory threshold `500 kB`; correctness,
  accessibility і production build gates зелені.

## Виправлення, знайдені фінальним gate

- UAT fixture test більше не залежить від порядку migration tests і явно створює
  потрібний confirmed status fixture;
- локальне provision користувача читає пароль лише з ignored credentials file та
  відкликає попередні сесії;
- Alpine test runtime запускає mypy без SQLite cache, оскільки production-only
  image навмисно не містить SQLite runtime;
- Vitest переведено на стабільний thread pool після відтвореного fork-worker
  shutdown hang;
- backend/web base images оновлено до patched Alpine runtimes;
- після виявленої несумісності nginx main config відновлено official include
  layout і production rehearsal повторно пройдено з нуля.
