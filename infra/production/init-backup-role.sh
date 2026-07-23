#!/bin/sh
set -eu

backup_user="$(cat /run/secrets/postgres_backup_user)"
backup_password="$(cat /run/secrets/postgres_backup_password)"

psql --set ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" \
  --dbname "${POSTGRES_DB}" \
  --set backup_user="${backup_user}" \
  --set backup_password="${backup_password}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'backup_user', :'backup_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'backup_user') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'backup_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'backup_user') \gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA public TO %I', :'backup_user') \gexec
SELECT format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'backup_user') \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON TABLES TO %I',
  current_user,
  :'backup_user'
) \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON SEQUENCES TO %I',
  current_user,
  :'backup_user'
) \gexec
SQL
