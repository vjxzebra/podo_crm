#!/bin/sh
set -eu

BASE_DIR=${PODORIA_BASE_DIR:-/opt/podoria-crm}
DEPLOY_USER=${PODORIA_DEPLOY_USER:-podoria-deploy}
SOURCE_ROOT=${PODORIA_SOURCE_ROOT:-$(CDPATH='' cd -- "$(dirname "$0")/../.." && pwd)}
DEPLOY_PUBLIC_KEY_FILE=${DEPLOY_PUBLIC_KEY_FILE:-}
INITIAL_ADMIN_CREDENTIALS_FILE=${INITIAL_ADMIN_CREDENTIALS_FILE:-}

[ "$(id -u)" -eq 0 ] || {
  echo "Production host bootstrap must run as root." >&2
  exit 2
}
[ -n "$DEPLOY_PUBLIC_KEY_FILE" ] && [ -s "$DEPLOY_PUBLIC_KEY_FILE" ] || {
  echo "DEPLOY_PUBLIC_KEY_FILE must point to a non-empty SSH public key." >&2
  exit 2
}
[ -n "$INITIAL_ADMIN_CREDENTIALS_FILE" ] && [ -s "$INITIAL_ADMIN_CREDENTIALS_FILE" ] || {
  echo "INITIAL_ADMIN_CREDENTIALS_FILE must point to a non-empty credentials file." >&2
  exit 2
}
for required_file in \
  scripts/operations/deploy-production.sh \
  scripts/operations/reset-production-database.sh \
  scripts/operations/reconcile-caddy.sh \
  infra/production/podoria-caddy-reconcile.service \
  infra/production/podoria-caddy-reconcile.timer \
  infra/production/crm.Caddyfile
do
  [ -f "$SOURCE_ROOT/$required_file" ] || {
    echo "Bootstrap source is missing: $required_file" >&2
    exit 2
  }
done

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi
usermod -aG docker "$DEPLOY_USER"
DEPLOY_GROUP=$(id -gn "$DEPLOY_USER")

install -d -m 0755 -o root -g root "$BASE_DIR"
for directory in incoming releases state; do
  install -d -m 0750 -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "$BASE_DIR/$directory"
done
install -d -m 0750 -o root -g "$DEPLOY_GROUP" \
  "$BASE_DIR/bin" "$BASE_DIR/shared" "$BASE_DIR/secrets"
install -d -m 0700 -o root -g root "$BASE_DIR/resets"

install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" "/home/$DEPLOY_USER/.ssh"
touch "/home/$DEPLOY_USER/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_GROUP" "/home/$DEPLOY_USER/.ssh/authorized_keys"
chmod 0600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
PUBLIC_KEY=$(cat "$DEPLOY_PUBLIC_KEY_FILE")
if ! grep -Fqx "$PUBLIC_KEY" "/home/$DEPLOY_USER/.ssh/authorized_keys"; then
  printf '%s\n' "$PUBLIC_KEY" >> "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi

install -m 0755 -o root -g root \
  "$SOURCE_ROOT/scripts/operations/deploy-production.sh" \
  "$BASE_DIR/bin/deploy-production.sh"
install -m 0750 -o root -g root \
  "$SOURCE_ROOT/scripts/operations/reset-production-database.sh" \
  "$BASE_DIR/bin/reset-production-database.sh"
install -m 0755 -o root -g root \
  "$SOURCE_ROOT/scripts/operations/reconcile-caddy.sh" \
  /usr/local/sbin/podoria-caddy-reconcile
install -m 0644 -o root -g root \
  "$SOURCE_ROOT/infra/production/podoria-caddy-reconcile.service" \
  /etc/systemd/system/podoria-caddy-reconcile.service
install -m 0644 -o root -g root \
  "$SOURCE_ROOT/infra/production/podoria-caddy-reconcile.timer" \
  /etc/systemd/system/podoria-caddy-reconcile.timer
install -m 0640 -o root -g "$DEPLOY_GROUP" \
  "$SOURCE_ROOT/infra/production/crm.Caddyfile" \
  "$BASE_DIR/shared/crm.Caddyfile"
install -m 0640 -o root -g "$DEPLOY_GROUP" \
  "$INITIAL_ADMIN_CREDENTIALS_FILE" \
  "$BASE_DIR/secrets/initial_admin_credentials"

generate_secret() {
  path=$1
  bytes=$2
  if [ ! -s "$path" ]; then
    umask 007
    openssl rand -base64 "$bytes" | tr -d '\n' > "$path"
    printf '\n' >> "$path"
  fi
  chown "root:$DEPLOY_GROUP" "$path"
  chmod 0640 "$path"
}

generate_secret "$BASE_DIR/secrets/django_secret_key" 64
generate_secret "$BASE_DIR/secrets/postgres_app_password" 36
if [ ! -s "$BASE_DIR/secrets/postgres_backup_user" ]; then
  printf 'podoria_backup\n' > "$BASE_DIR/secrets/postgres_backup_user"
fi
chown "root:$DEPLOY_GROUP" "$BASE_DIR/secrets/postgres_backup_user"
chmod 0640 "$BASE_DIR/secrets/postgres_backup_user"
generate_secret "$BASE_DIR/secrets/postgres_backup_password" 36
if [ ! -s "$BASE_DIR/secrets/minio_root_user" ]; then
  printf 'podoria_minio_root\n' > "$BASE_DIR/secrets/minio_root_user"
fi
chown "root:$DEPLOY_GROUP" "$BASE_DIR/secrets/minio_root_user"
chmod 0640 "$BASE_DIR/secrets/minio_root_user"
generate_secret "$BASE_DIR/secrets/minio_root_password" 40
if [ ! -s "$BASE_DIR/secrets/minio_app_access_key" ]; then
  printf 'podoria-app-%s\n' "$(openssl rand -hex 8)" \
    > "$BASE_DIR/secrets/minio_app_access_key"
fi
chown "root:$DEPLOY_GROUP" "$BASE_DIR/secrets/minio_app_access_key"
chmod 0640 "$BASE_DIR/secrets/minio_app_access_key"
generate_secret "$BASE_DIR/secrets/minio_app_secret_key" 40
if [ ! -s "$BASE_DIR/secrets/minio_backup_access_key" ]; then
  printf 'podoria-backup-%s\n' "$(openssl rand -hex 8)" \
    > "$BASE_DIR/secrets/minio_backup_access_key"
fi
chown "root:$DEPLOY_GROUP" "$BASE_DIR/secrets/minio_backup_access_key"
chmod 0640 "$BASE_DIR/secrets/minio_backup_access_key"
generate_secret "$BASE_DIR/secrets/minio_backup_secret_key" 40

if [ ! -s "$BASE_DIR/shared/production.env" ]; then
  umask 0027
  {
    printf 'COMPOSE_PROJECT_NAME=podoria-production\n'
    printf 'EDGE_NETWORK_NAME=podoria-edge\n'
    printf 'APP_BIND_ADDRESS=127.0.0.1\n'
    printf 'APP_PORT=8088\n'
    printf 'DJANGO_ALLOWED_HOSTS=crm.rozhenko.km.ua,backend,proxy,localhost,127.0.0.1\n'
    printf 'DJANGO_CSRF_TRUSTED_ORIGINS=https://crm.rozhenko.km.ua\n'
    printf 'DJANGO_SECURE_SSL_REDIRECT=1\n'
    printf 'DJANGO_SECURE_HSTS_SECONDS=31536000\n'
    printf 'DJANGO_SECURE_HSTS_PRELOAD=0\n'
    printf 'SESSION_IDLE_TIMEOUT_SECONDS=1800\n'
    printf 'SESSION_ABSOLUTE_TIMEOUT_SECONDS=43200\n'
    printf 'LOGIN_RATE_LIMIT_WINDOW_SECONDS=900\n'
    printf 'LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS=5\n'
    printf 'LOGIN_RATE_LIMIT_IP_ATTEMPTS=30\n'
    printf 'POSTGRES_DB=podoria\n'
    printf 'POSTGRES_USER=podoria\n'
    printf 'MINIO_BUCKET_NAME=podoria-private\n'
    printf 'WEB_CONCURRENCY=2\n'
    printf 'CELERY_WORKER_CONCURRENCY=1\n'
  } > "$BASE_DIR/shared/production.env"
fi
chown "root:$DEPLOY_GROUP" "$BASE_DIR/shared/production.env"
chmod 0640 "$BASE_DIR/shared/production.env"

docker network inspect podoria-edge >/dev/null 2>&1 \
  || docker network create podoria-edge >/dev/null
systemctl daemon-reload

printf '{"status":"bootstrapped","base_dir":"%s","deploy_user":"%s"}\n' \
  "$BASE_DIR" "$DEPLOY_USER"
