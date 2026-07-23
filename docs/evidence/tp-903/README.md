# TP-903 backup/deployment evidence

Дата: 2026-07-22. Контракт: [TP-903 backup/deployment](../../architecture/tp-903-backup-deployment-contract.md).

## Backup і retention

- Фінальний quiesced dev recovery point `20260722T214238Z` створений через operations
  container без host crypto dependency: encrypted archive `921212` bytes, SHA-256
  `56f2ff60e6e92e23d84266ce7bd89453e5e4219dd179fe61f5fc68053a8483be`.
- Manifest: PostgreSQL custom dump `229798` bytes, `53` migrations; private MinIO snapshot
  `10` objects / `937233` bytes. Plaintext stage відсутній, daily/monthly мають archive та
  обидва sidecars.
- Wrong restore token завершився `78`; навмисно пошкоджена encrypted fixture була відхилена
  checksum gate до decrypt/target connection.
- Retention fixture: dry-run визначив рівно `5` removals; actual лишив `30` daily і `12`
  monthly archives, кожен із двома sidecars (`126` files).
- Фінальний ops image `sha256:2ea777756e71135c0e0f0f9b649f284d8c330349f5ddac13f17dc4f6979fa98f`
  використовує `age 1.3.1`, PostgreSQL client `17.10`, Python `3.14.6` і MinIO SDK
  `7.2.20`; Docker Scout проіндексував `81` package та знайшов `0C/0H/0M/0L`.

## Isolated restore

- Restore у tmpfs PostgreSQL/MinIO завершився за `8.3s`.
- Manifest/restored counts збіглися: `53` migrations, `10` objects.
- `verify_restore`: status `ok`, `10` persisted object references, `0` missing objects,
  `0` pending migrations, `0` invalid constraints.
- Exact drill containers і tmpfs data видалені; dev domain data не змінювались.

## Deployment і rollback

- Production-like Compose використав окремий project/port/volumes, no source bind mounts,
  random file-mounted rehearsal secrets і distinct immutable backend/web image IDs.
- Deployment state був прив'язаний до перевіреного manifest recovery point
  `20260722T210700Z`; mismatch або відсутній manifest блокує preflight до Compose mutation.
- Candidate deploy: `53` migrations, MinIO app/backup identities, backend/web healthy,
  worker/beat running; root/readiness/session smoke — `200/200/401`.
- PostgreSQL backup role: `SELECT=true`, `INSERT=false`, `DELETE=false` для
  `django_migrations`. MinIO backup policy дозволяє тільки bucket list/location та object get;
  application services не мають backup target/decrypt identity.
- Image-only rollback повернув previous backend/web IDs без reverse migration; повторний smoke
  — `200/200/401`, migration/seed invariants лишилися `53/1`.
- Перший provisioning run виявив відсутній `sed` у minimal MinIO client image. Policy renderer
  переведено на POSIX shell builtins; повторний run пройшов без reset. Перший rollback switch
  і smoke пройшли, але state serialization не могла додати нові `PSCustomObject` fields;
  `Add-Member` fix та idempotent rerun записали canonical `rolled_back` state.
- Після evidence exact release project, його containers/network/volumes, encrypted drill
  fixture та ephemeral `age` identity видалені; основний dev stack/volumes не змінювались.

## Canonical quality gate

- Backend: `357/357`; frontend: `198/198`; component axe: `40/40`.
- Ruff/format: `243` Python files; mypy: `187` source files; Django, fresh migrations,
  OpenAPI/generated contracts, lint, strict typecheck і production build — green.

Machine-readable summary: [operations-gate.json](operations-gate.json).
