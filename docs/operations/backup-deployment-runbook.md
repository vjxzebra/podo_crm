# Backup, restore, deployment and rollback runbook

Цей runbook реалізує [TP-903 contract](../architecture/tp-903-backup-deployment-contract.md)
та [ADR-005](../architecture/decisions/0005-backup-and-restore-policy.md). Команди запускає
operations owner з host, де доступний Docker Compose. Реальні secrets існують лише поза
репозиторієм у secret manager або локальних ignored files.

## Recovery objectives і schedule

- RPO: не більше 24 годин; encrypted backup запускається щодня після завершення клінічного дня.
- RTO: не більше 4 годин на підготовленій інфраструктурі.
- Retention: 30 daily та 12 monthly recovery points.
- Isolated restore drill: щомісяця та перед production launch.
- Redis, Celery queues, derived previews і images не backup-яться окремо. Business truth —
  PostgreSQL і приватний MinIO bucket.

Alert є обов'язковим, якщо job nonzero, останній daily archive старший за 26 годин, archive
або sidecar порожній/відсутній, encrypted SHA-256 не збігається, розмір різко відхилився від
попереднього recovery point або monthly drill прострочений понад 35 днів.

## Secret files

Production application directory (`PODORIA_SECRET_DIR`) містить рівно такі files:

```text
django_secret_key
postgres_app_password
postgres_backup_user
postgres_backup_password
minio_root_user
minio_root_password
minio_app_access_key
minio_app_secret_key
minio_backup_access_key
minio_backup_secret_key
```

Backup job використовує інший directory (`BACKUP_SECRET_DIR`):

```text
backup_postgres_password
backup_minio_access_key
backup_minio_secret_key
age_recipient.txt
```

Restore operator тимчасово додає до свого isolated secret directory:

```text
restore_postgres_password
restore_minio_access_key
restore_minio_secret_key
age_identity.txt
```

`age_identity.txt` зберігається offline/у recovery secret manager і не монтується в backup
job або application. Public recipient можна створити operations image:

```powershell
docker build -t podoria-crm-ops infra/ops
docker run --rm `
  -e AGE_IDENTITY_OUTPUT=/keys/age_identity.txt `
  -e AGE_RECIPIENT_OUTPUT=/keys/age_recipient.txt `
  -v "C:/secure/podoria-recovery:/keys" `
  podoria-crm-ops generate-key
```

Не вставляйте secret value у command line, документацію, deployment state або evidence.

Перед публікацією operations image перевірте його runtime dependencies; release gate не
приймає critical/high findings:

```powershell
docker build --pull -t podoria-crm-ops infra/ops
docker scout cves --only-severity critical,high --exit-code podoria-crm-ops
```

MinIO snapshot виконує pinned Python SDK усередині image, а `age` збирається з перевіреного
release source; host не потребує цих CLI/runtime dependencies.

## Daily backup

`BACKUP_TARGET_PATH` у production має бути mount іншого failure domain. Перед snapshot wrapper
запам'ятовує running services, зупиняє proxy → worker/beat → backend, запускає encrypted
backup, а у `finally` відновлює лише раніше запущені services.

```powershell
./scripts/operations/backup.ps1 `
  -TargetPath $env:BACKUP_TARGET_PATH `
  -SecretDirectory $env:BACKUP_SECRET_DIR `
  -OffHost
```

Успішний job повертає один JSON event. Recovery point є валідним лише з трьома files:

```text
daily/podoria-YYYYMMDDTHHMMSSZ.tar.gz.age
daily/podoria-YYYYMMDDTHHMMSSZ.tar.gz.age.sha256
daily/podoria-YYYYMMDDTHHMMSSZ.tar.gz.age.manifest.json
```

Plaintext stage видаляється trap-ом; `.partial` не публікується як готовий archive. Перший
успішний backup місяця копіюється в `monthly/`. Retention можна перевірити без mutation:

```powershell
$env:RETENTION_DRY_RUN = "1"
docker compose -f compose.yaml -f compose.ops.yaml --profile ops run --rm retention-ops
```

## Isolated restore drill

Restore ніколи не спрямовується на live targets. Wrapper піднімає PostgreSQL/MinIO без host
ports на tmpfs, перевіряє encrypted checksum, exact `restore:<id>` token, archive paths і
payload checksums, вимагає empty targets, а після restore запускає `verify_restore`.

```powershell
./scripts/operations/restore-drill.ps1 `
  -TargetPath $env:BACKUP_TARGET_PATH `
  -SecretDirectory C:/secure/podoria-restore-drill `
  -ArchivePath X:/podoria-off-host-backups/daily/podoria-YYYYMMDDTHHMMSSZ.tar.gz.age `
  -BackendImage registry.example/podoria-backend@sha256:...
```

Gate вимагає однакові manifest/restored migration та object counts, нуль pending migrations,
invalid constraints і missing clinic-logo/visit-photo/preview references. Wrapper у `finally`
видаляє тільки exact restore containers; tmpfs data не переживає drill.

## Production deployment

`compose.production.yaml` не має source bind mounts. Backend/web задаються immutable registry
digest або локальним image id; application отримує лише file secrets. PostgreSQL backup role
має read-only grants, MinIO backup user — `List/Get`, application не бачить off-host target.

Перед deployment:

1. Перевірте latest backup JSON, checksum і вкажіть його recovery-point id.
2. Перевірте вільне місце, Docker health і доступність candidate/previous images.
3. Підтвердьте HTTPS termination та `X-Forwarded-Proto`. `DJANGO_SECURE_HSTS_PRELOAD=1`
   дозволено лише коли production domain і всі subdomains постійно HTTPS-ready.
4. Збережіть deployment state поза репозиторієм.

```powershell
./scripts/operations/deploy.ps1 `
  -BackendImage registry.example/podoria-backend@sha256:... `
  -WebImage registry.example/podoria-web@sha256:... `
  -PreviousBackendImage registry.example/podoria-backend@sha256:... `
  -PreviousWebImage registry.example/podoria-web@sha256:... `
  -SecretDirectory C:/secure/podoria-production `
  -StatePath C:/secure/podoria-deployments/release.json `
  -RecoveryPointId YYYYMMDDTHHMMSSZ `
  -RecoveryPointManifestPath X:/podoria-off-host-backups/daily/podoria-YYYYMMDDTHHMMSSZ.tar.gz.age.manifest.json
```

Script виконує Compose preflight, dependency health, idempotent MinIO identities, один migration
job, `check --deploy`, backend/web health, worker/beat start, proxy switch і smoke `200/200/401`.
Migrations перед rolling restart мають бути backward-compatible з previous image.

## Rollback

Звичайний rollback не reverse-ить migrations. Він бере previous image IDs із deployment state,
перемикає backend/web/worker/beat, перезапускає proxy та повторює `200/200/401` smoke:

```powershell
./scripts/operations/rollback.ps1 `
  -StatePath C:/secure/podoria-deployments/release.json `
  -SecretDirectory C:/secure/podoria-production
```

Reverse migration дозволена лише після окремої перевірки reversibility, відсутності
несумісних writes і incident approval. Якщо old app несумісний із forward schema/data,
залишайте maintenance mode та виконуйте повний recovery-point restore на підготовлені empty
targets. Не редагуйте частково production DB/object store вручну.

## Operational log

Зберігайте backup/restore/deploy/rollback JSON events у restricted operations log із timestamp,
operator identity, recovery point, image digests, sizes/counts/checksums і result. Не записуйте
passwords, private keys, cookies, object keys або patient fields.
