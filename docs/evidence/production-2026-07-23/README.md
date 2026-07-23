# Production deployment evidence — 2026-07-23

## Scope

- CRM: `https://crm.rozhenko.km.ua`
- Existing WordPress: `https://rozhenko.km.ua`
- Host: `45.129.99.211`
- Initial verified release:
  `3146b09d89ceac56fd53818a41868bde50ce5e32`

The initial release was uploaded as SHA-256-verified source and Docker image
archives. CRM runs as Compose project `podoria-production`; the existing
WordPress project `podo` and its MariaDB volume were not modified.

## Live verification

| Check | Result |
| --- | --- |
| CRM DNS A answer | `45.129.99.211` |
| WordPress DNS A answer | `45.129.99.211` |
| CRM root | HTTP `200` |
| CRM readiness | HTTP `200` |
| Anonymous session API | HTTP `401` |
| Initial admin login | HTTP `200`, role `admin` |
| Authenticated admin session | HTTP `200` |
| WordPress root | HTTP `200` |
| WordPress login | HTTP `200` |
| HSTS | `max-age=31536000; includeSubDomains` |
| CSP | present |
| CRM proxy bind | `127.0.0.1:8088` only |
| Caddy reconcile timer | enabled and active |

The server-side TLS check returned a Let's Encrypt certificate with
`DNS:crm.rozhenko.km.ua`, valid from 2026-07-23 through 2026-10-21.

All CRM infrastructure services were healthy. Backend, web, and proxy health
checks were healthy; Celery worker and beat were running. The PostgreSQL backup
role existed after initialization.

## Administrator and reset safety

The first administrator was provisioned as `admin@crm.rozhenko.km.ua`.
The credential value is intentionally not recorded in Git.

The production reset script was tested only with an invalid confirmation token
and exited with status `2` before mutation. A real reset was not executed after
creating the administrator.

## Autodeploy

The GitHub `Quality gate` workflow deploys only after the test profile succeeds
on a push to `main`. The following repository secrets were configured:

- `PROD_SSH_HOST`
- `PROD_SSH_USER`
- `PROD_SSH_PRIVATE_KEY`
- `PROD_SSH_KNOWN_HOSTS`

The workflow uses the dedicated `podoria-deploy` account, an ED25519 deploy
key, and pinned host-key verification. No root password is stored in GitHub.
