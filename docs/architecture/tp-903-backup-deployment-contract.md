# TP-903 — backup, restore, deployment and rollback contract

Дата фіксації: 2026-07-22. Джерело рішення: [ADR-005](decisions/0005-backup-and-restore-policy.md).

## Межі пакета

TP-903 додає provider-neutral operations layer для поточного single-host Docker Compose
deployment. Пакет не додає CRM-екранів, не backup-ить Redis/Celery queues і не обирає
конкретний cloud/provider. Production має монтувати backup target з іншого failure domain;
локальний каталог дозволений лише для позначеного rehearsal.

## Recovery point

- Один recovery point містить PostgreSQL custom-format dump, повний snapshot приватного
  MinIO bucket, payload checksums і machine-readable manifest.
- Proxy, backend, worker і beat зупиняються у короткому maintenance window до snapshot;
  PostgreSQL та MinIO лишаються healthy. Це не дозволяє DB reference з'явитися між object
  snapshot і DB dump.
- Plaintext stage завжди видаляється. Готовий archive шифрується `age` до окремого public
  recipient; private identity не доступна application services або backup job.
- Archive публікується атомарно лише після size/checksum validation. Незавершені `.partial`
  файли не є recovery points.
- Backup target вважається production-valid лише після explicit
  `BACKUP_TARGET_IS_OFFHOST=1`. `ALLOW_LOCAL_BACKUP_TARGET=1` існує тільки для drill.
- Retention: 30 daily та 12 monthly recovery points. Monthly promotion виконується для
  першого успішного backup календарного місяця; retention видаляє лише validated artifacts
  у відповідних `daily/` і `monthly/` каталогах.

Цілі ADR-005: `RPO ≤ 24h`, `RTO ≤ 4h`. Daily job, alert на пропущений/пошкоджений archive
та monthly isolated restore drill є release operations requirements.

## Credentials і privacy

- Application, PostgreSQL backup reader, MinIO backup reader, restore operator та `age`
  identity мають окремі credentials.
- Production secrets монтуються як files; жоден tracked файл або command line не містить
  реальних password/token/private key values.
- Application containers не отримують off-host target credentials або decrypt identity.
- Manifest не містить object keys, patient data або credentials; operational log містить
  тільки recovery-point id, timestamps, sizes, counts, checksums і result.

## Restore gate

- Restore приймає один `.tar.gz.age`, перевіряє encrypted checksum до decrypt, відхиляє
  unsafe archive paths і перевіряє всі payload checksums до mutation target-ів.
- За замовчуванням target PostgreSQL schema і MinIO bucket мають бути порожніми. Replace
  потребує окремого explicit override та maintenance/incident procedure.
- Mutation починається лише з exact token `restore:<recovery-point-id>`.
- Після restore запускаються Django system check, migration plan, DB constraints і
  `verify_restore`: кожен clinic-logo, visit-photo original та persisted preview reference
  повинен мати object. PROCESSING previews без persisted key повторно ставляться в queue
  після запуску worker; Redis і старі queues не відновлюються.
- Drill використовує ephemeral isolated PostgreSQL/MinIO targets без host ports і після
  evidence cleanup видаляє тільки exact drill containers/tmpfs data.

## Deployment order

1. Перевірити immutable backend/web image refs, secret files, disk і healthy dependencies.
2. Створити та перевірити recovery point.
3. Запустити candidate image `check --deploy` і `migrate --plan`.
4. Запустити рівно один migration job; migrations мусять бути backward-compatible з
   попереднім app image на час rolling restart.
5. Оновити backend, worker, beat і web; proxy перемкнути/перезапустити останнім.
6. Перевірити live/readiness, unauthenticated session boundary, static asset і worker.
7. Записати deployed/previous digests та smoke result в operational evidence.

## Rollback policy

- Перший rollback — повернення попередніх immutable app image refs і restart proxy. Forward
  DB migrations залишаються applied, якщо old image сумісний.
- Reverse migration не виконується автоматично. Вона дозволена лише якщо migration явно
  перевірена як reversible, після deploy не було несумісних writes і є incident approval.
- Якщо schema/data несумісні, застосовується повний encrypted recovery point restore під
  maintenance window, а не часткове ручне редагування DB/objects.
- Rollback успішний лише після тих самих smoke/readiness gates, що й deployment.

## Exit criteria

- Backup archive encrypted, non-empty, checksum-valid; retention dry-run/fixture gate green.
- Isolated restore відтворює DB migration count і object count, не має missing references,
  pending migrations або constraint errors.
- Candidate deploy і image-only rollback пройшли на production-like Compose без bind mounts;
  app data/volumes survive rollback.
- Canonical backend/frontend gates, dependency/security checks і runtime smoke лишаються green.
