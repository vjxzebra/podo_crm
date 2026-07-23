# Production CRM на спільному WordPress-сервері

Дата фіксації: 2026-07-23

## Межі deployment

- WordPress `rozhenko.km.ua` лишається у Compose-проєкті `podo` в `/opt/podo`.
- CRM `crm.rozhenko.km.ua` працює у проєкті `podoria-production` в
  `/opt/podoria-crm`.
- CRM має власні PostgreSQL, Redis і MinIO volumes. Жоден CRM command не
  звертається до MariaDB або WordPress volumes.
- Існуючий `podo-caddy-1` лишається єдиним listener на `80/443`.
  `podoria-caddy-reconcile.timer` приєднує його до external network
  `podoria-edge` і reload-ить поточний `/opt/podo/Caddyfile` разом із окремим
  CRM fragment. Тому WordPress source/deploy не редагується.
- Внутрішній CRM proxy додатково доступний лише на `127.0.0.1:8088` для
  emergency smoke; database/object-store ports назовні не публікуються.

## Production layout

```text
/opt/podoria-crm/
  bin/                  # root-installed deploy/reset/reconcile entrypoints
  incoming/             # GitHub Actions release archives
  releases/<sha>/       # immutable source snapshots
  current -> releases/<sha>
  shared/
    production.env      # non-secret production settings
    crm.Caddyfile       # isolated subdomain route
  secrets/              # 0750 root/deploy directory; read-only file mounts for non-root containers
  state/                # deployment result JSON
  resets/               # root-only pre-reset pg_dump snapshots
```

## Autodeploy

`Quality gate` спочатку виконує canonical Docker tests. Лише успішний
`push` у `main` запускає `deploy-production`:

1. будує backend/web images із exact `GITHUB_SHA`;
2. пакує git archive та Docker image archive з SHA-256 sidecars;
3. передає їх окремим SSH deploy key;
4. remote script перевіряє archive paths/checksums, завантажує images,
   виконує migrations і `check --deploy`;
5. перемикає backend/web/worker/beat/proxy, reconciles Caddy;
6. перевіряє CRM `200/401` та повторно WordPress `200`;
7. тільки після green smoke атомарно оновлює `current`.

GitHub repository secrets:

```text
PROD_SSH_HOST
PROD_SSH_USER
PROD_SSH_PRIVATE_KEY
PROD_SSH_KNOWN_HOSTS
```

Password SSH у GitHub не зберігається.

Початковий host bootstrap виконується root-користувачем із deployment source,
окремим public deploy key та credentials file першого admin:

```sh
DEPLOY_PUBLIC_KEY_FILE=/root/bootstrap/podoria-deploy.pub \
INITIAL_ADMIN_CREDENTIALS_FILE=/root/bootstrap/initial-admin.env \
  ./scripts/operations/bootstrap-production-host.sh
```

Bootstrap створює `podoria-deploy`, додає його до Docker group, генерує
production secrets з `openssl`, встановлює root-owned deploy/reset/reconcile
entrypoints і не виводить secret values.

## Перший адміністратор

`provision_initial_admin` читає email/password лише з credentials file,
працює тільки коли таблиця користувачів порожня, застосовує Django password
validators і створює audit event без password value:

```sh
docker compose ... run --rm --no-deps \
  -v /opt/podoria-crm/secrets/initial_admin_credentials:/run/secrets/initial_admin_credentials:ro \
  backend python manage.py provision_initial_admin \
  --credentials-file /run/secrets/initial_admin_credentials
```

## Експериментальний reset database

Reset не запускається без exact confirmation token. Перед mutation він створює
root-only compressed `pg_dump`, зупиняє лише CRM app services, drop/create
тільки CRM database, очищає CRM Redis, повторює migrations і smoke. MinIO та
WordPress не змінюються.

Порожня database:

```sh
sudo /opt/podoria-crm/bin/reset-production-database.sh \
  --confirm RESET_PODORIA_CRM_DATABASE
```

Database з повторним bootstrap першого admin із production credentials:

```sh
sudo /opt/podoria-crm/bin/reset-production-database.sh \
  --confirm RESET_PODORIA_CRM_DATABASE \
  --with-admin
```

`--with-admin` спрацює лише після повного reset, бо command відмовляється
працювати, якщо вже існує будь-який користувач.

## Rollback і перевірка

При невдалому deploy remote script намагається повернути previous backend/web
image IDs і попередній release config, не reverse-ить migrations та записує
`state/<sha>.failed.json`. Після ручного втручання обов’язково:

```sh
curl -fsS https://crm.rozhenko.km.ua/health/ready
curl -fsS https://rozhenko.km.ua/ >/dev/null
docker compose -p podoria-production ps -a
systemctl status podoria-caddy-reconcile.timer
```

Локальні pre-reset dumps не замінюють off-host backup із головного
[backup/deployment runbook](backup-deployment-runbook.md).
