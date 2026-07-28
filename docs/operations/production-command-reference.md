# Production command reference

Це практичний довідник команд для CRM `crm.rozhenko.km.ua`, яка працює на
тому самому сервері, що й WordPress `rozhenko.km.ua`. Архітектурні межі та
пояснення deployment наведені у
[production CRM runbook](production-crm-runbook.md), а backup/restore —
у [backup runbook](backup-deployment-runbook.md). Telegram rollout після
TP-1011 описаний в [Telegram runbook](telegram-rollout-runbook.md).

## Правила безпеки

- Реальні паролі, private keys, cookies і токени не вставляються в команди,
  tracked-документацію, deployment state або GitHub logs.
- Локальні credentials зберігаються тільки в ignored `.env.local` чи
  `.env.production.local`; production secrets — у `/opt/podoria-crm/secrets`.
- GitHub використовує окремий SSH deploy key користувача `podoria-deploy`.
  Root password у GitHub не зберігається.
- Усі destructive CRM-команди мають exact confirmation token. Вони не
  звертаються до `/opt/podo`, MariaDB або WordPress volumes.
- Demo-дані містять вигадані ПІБ, контакти, медичні відомості та фінансові
  операції. Не використовуйте їх як реальні дані пацієнтів.

## DNS, HTTPS і базова перевірка

PowerShell:

```powershell
Resolve-DnsName crm.rozhenko.km.ua
curl.exe --fail --silent --show-error https://crm.rozhenko.km.ua/health/ready
curl.exe --fail --silent --show-error https://rozhenko.km.ua/ --output NUL
```

На production host:

```sh
curl -fsS --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/health/ready
curl -fsS --resolve rozhenko.km.ua:443:127.0.0.1 \
  https://rozhenko.km.ua/ >/dev/null
docker compose -p podoria-production ps -a
systemctl status podoria-caddy-reconcile.timer
```

Очікуваний CRM readiness — HTTP `200`, WordPress — HTTP `200`.

## Початковий bootstrap production host

Підготуйте поза репозиторієм:

- SSH public key для `podoria-deploy`;
- credentials file першого адміністратора з mode `0600`:

```dotenv
PODORIA_INITIAL_ADMIN_EMAIL=admin@example.invalid
PODORIA_INITIAL_ADMIN_PASSWORD=replace-with-a-unique-secret
```

Запускати з checkout deployment source як `root`:

```sh
chmod 0600 /root/bootstrap/initial-admin.env
DEPLOY_PUBLIC_KEY_FILE=/root/bootstrap/podoria-deploy.pub \
INITIAL_ADMIN_CREDENTIALS_FILE=/root/bootstrap/initial-admin.env \
  ./scripts/operations/bootstrap-production-host.sh

systemctl enable --now podoria-caddy-reconcile.timer
/usr/local/sbin/podoria-caddy-reconcile
```

Bootstrap:

- створює `/opt/podoria-crm`, користувача `podoria-deploy` і external Docker
  network `podoria-edge`;
- генерує file-backed application/backup/MinIO secrets;
- встановлює deploy, reset, demo-seed і Caddy entrypoints;
- не змінює WordPress checkout або WordPress Caddyfile.

## GitHub secrets і autodeploy

Required repository secrets:

```text
PROD_SSH_HOST
PROD_SSH_USER
PROD_SSH_PRIVATE_KEY
PROD_SSH_KNOWN_HOSTS
```

Приклад без виведення secret values у консоль:

```powershell
gh secret set PROD_SSH_HOST --body "45.129.99.211"
gh secret set PROD_SSH_USER --body "podoria-deploy"
gh secret set PROD_SSH_PRIVATE_KEY --body (Get-Content C:\secure\podoria-deploy -Raw)
gh secret set PROD_SSH_KNOWN_HOSTS --body (Get-Content C:\secure\podoria-known-hosts -Raw)
gh secret list
```

Кожен успішний `push` у `main` спочатку запускає canonical quality gate, а
потім job `deploy-production`:

```powershell
git push origin main
gh run list --workflow ci.yml --branch main --limit 5
gh run watch <run-id> --exit-status
```

Перевірка конкретного deployed release на host:

```sh
readlink -f /opt/podoria-crm/current
ls -lt /opt/podoria-crm/state
cat /opt/podoria-crm/state/<40-char-commit-sha>.json
```

## Ручний artifact deploy

Звичайний шлях — autodeploy. Для контрольованого ручного повтору вже
завантажені source/image archives та їх `.sha256` sidecars мають лежати в
`/opt/podoria-crm/incoming`:

```sh
/opt/podoria-crm/bin/deploy-production.sh \
  <40-char-commit-sha> \
  /opt/podoria-crm/incoming/podoria-source-<sha>.tar.gz \
  /opt/podoria-crm/incoming/podoria-images-<sha>.tar.gz
```

Скрипт перевіряє SHA-256, виконує migrations і `check --deploy`, перемикає
контейнери, reconciles Caddy та перевіряє CRM/WordPress. При помилці він
намагається повернути попередні images і записує `<sha>.failed.json`.
Reverse migration автоматично не виконується.

## Перший адміністратор

Bootstrap зберігає credentials як
`/opt/podoria-crm/secrets/initial_admin_credentials`. Після першого deploy
користувача можна створити рівно один раз у порожній таблиці:

```sh
BASE_DIR=/opt/podoria-crm
CURRENT_RELEASE=$(readlink -f "$BASE_DIR/current")
set -a
. "$BASE_DIR/shared/production.env"
set +a
export PODORIA_SECRET_DIR="$BASE_DIR/secrets"
export BACKEND_IMAGE=$(docker inspect podoria-production-backend-1 --format '{{.Image}}')
export WEB_IMAGE=$(docker inspect podoria-production-web-1 --format '{{.Image}}')

docker compose \
  --env-file "$BASE_DIR/shared/production.env" \
  -f "$CURRENT_RELEASE/compose.production.yaml" \
  -f "$CURRENT_RELEASE/compose.edge.yaml" \
  run --rm --no-deps \
  -v "$BASE_DIR/secrets/initial_admin_credentials:/run/secrets/initial_admin_credentials:ro" \
  backend python manage.py provision_initial_admin \
  --credentials-file /run/secrets/initial_admin_credentials
```

Команда читає пароль лише з mounted file, застосовує Django password
validators і відмовляється змінювати наявних користувачів.

## Demo fixtures

Management command створює детермінований cross-domain набір і приймає
тільки exact token:

```sh
python manage.py seed_demo_data \
  --confirm SEED_PODORIA_DEMO_DATA \
  --scale large
```

Production wrapper:

```sh
sudo /opt/podoria-crm/bin/seed-production-demo-data.sh \
  --confirm SEED_PODORIA_DEMO_DATA \
  --scale large
```

Доступні масштаби:

| Scale | Patients | Appointments | Materials | Suppliers | Services | Rooms | Work items | Photo visits | Podologists | Receptionists |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `small` | 12 | 28 | 8 | 3 | 6 | 2 | 16 | 2 | 2 | 1 |
| `large` | 140 | 360 | 36 | 10 | 12 | 4 | 90 | 20 | 4 | 3 |

Seed заповнює:

- профіль клініки, кімнати, послуги, статуси й команду;
- пацієнтів, медичні профілі, календар і всі основні appointment states;
- прийоми, examination, conditions, recommendations і приватні фото
  `BEFORE/AFTER` разом із previews у MinIO;
- постачальників, матеріали, партії, надходження, списання, використання на
  візитах, рухи та інвентаризацію;
- receivables, cash/card payments, refunds, відкриті/закриті касові зміни,
  внесення й вилучення готівки;
- справи, сповіщення й audit events; overview, analytics і global search
  використовують ці ж записи.

Перед першим запуском потрібен активний initial superuser і порожня domain
database. Наявність пацієнтів, записів, матеріалів, операцій, справ чи
неадміністративних користувачів блокує seed і підказує виконати guarded reset.

Операція розбита на resumable transaction phases. Повтор із тим самим
`--scale` після успіху безпечний і повертає `status=already_seeded`; інший
scale потребує reset. Demo-акаунти мають unusable passwords і не можуть
увійти. Для огляду всіх даних використовується initial admin.

Локальний запуск у чистій dev-базі:

```powershell
docker compose run --rm backend python manage.py seed_demo_data `
  --confirm SEED_PODORIA_DEMO_DATA `
  --scale small
```

## Guarded reset

Перед reset автоматично створюється root-only compressed `pg_dump` у
`/opt/podoria-crm/resets`. Reset очищає лише CRM PostgreSQL database і CRM
Redis DB; MinIO та WordPress не змінюються.

Порожня CRM database:

```sh
sudo /opt/podoria-crm/bin/reset-production-database.sh \
  --confirm RESET_PODORIA_CRM_DATABASE
```

Порожня CRM database з повторним створенням initial admin:

```sh
sudo /opt/podoria-crm/bin/reset-production-database.sh \
  --confirm RESET_PODORIA_CRM_DATABASE \
  --with-admin
```

Повний цикл для нового великого demo-набору:

```sh
sudo /opt/podoria-crm/bin/reset-production-database.sh \
  --confirm RESET_PODORIA_CRM_DATABASE \
  --with-admin

sudo /opt/podoria-crm/bin/seed-production-demo-data.sh \
  --confirm SEED_PODORIA_DEMO_DATA \
  --scale large
```

`--with-admin` використовує наявний protected credentials file. Якщо його
потрібно замінити, спочатку безпечно оновіть
`/opt/podoria-crm/secrets/initial_admin_credentials` з mode `0444`,
власником `root` і deploy group; не вставляйте пароль у shell history.

## Caddy і діагностика

Ручний reconcile:

```sh
sudo /usr/local/sbin/podoria-caddy-reconcile
systemctl status podoria-caddy-reconcile.timer
journalctl -u podoria-caddy-reconcile.service -n 100 --no-pager
docker network inspect podoria-edge
```

CRM containers і logs:

```sh
docker compose -p podoria-production ps -a
docker logs --tail 200 podoria-production-backend-1
docker logs --tail 200 podoria-production-worker-1
docker logs --tail 200 podoria-production-proxy-1
```

Після будь-якого ручного втручання повторіть:

```sh
curl -fsS http://127.0.0.1:8088/health/ready
curl -fsS --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/health/ready
curl -fsS --resolve rozhenko.km.ua:443:127.0.0.1 \
  https://rozhenko.km.ua/ >/dev/null
```

## Локальні перевірки перед push

PowerShell:

```powershell
docker compose config
.\scripts\run-tests.ps1
git diff --check
```

Linux/macOS:

```sh
docker compose config
sh ./scripts/run-tests.sh
git diff --check
```

Canonical gate охоплює Ruff, format, mypy, Django checks/migrations, pytest,
OpenAPI/client generation, ESLint, TypeScript, frontend tests і production
build.
