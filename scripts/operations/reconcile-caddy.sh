#!/bin/sh
set -eu

CADDY_CONTAINER=${CADDY_CONTAINER:-podo-caddy-1}
EDGE_NETWORK_NAME=${EDGE_NETWORK_NAME:-podoria-edge}
WORDPRESS_CADDYFILE=${WORDPRESS_CADDYFILE:-/opt/podo/Caddyfile}
CRM_CADDY_FRAGMENT=${CRM_CADDY_FRAGMENT:-/opt/podoria-crm/shared/crm.Caddyfile}

[ -s "$WORDPRESS_CADDYFILE" ] || {
  echo "WordPress Caddyfile is missing." >&2
  exit 1
}
[ -s "$CRM_CADDY_FRAGMENT" ] || {
  echo "CRM Caddy fragment is missing." >&2
  exit 1
}
docker inspect "$CADDY_CONTAINER" >/dev/null
docker network inspect "$EDGE_NETWORK_NAME" >/dev/null 2>&1 \
  || docker network create "$EDGE_NETWORK_NAME" >/dev/null
if ! docker inspect "$CADDY_CONTAINER" --format '{{json .NetworkSettings.Networks}}' \
  | grep -q "\"$EDGE_NETWORK_NAME\""
then
  docker network connect "$EDGE_NETWORK_NAME" "$CADDY_CONTAINER"
fi

TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM
cp "$WORDPRESS_CADDYFILE" "$TEMP_FILE"
printf '\n' >> "$TEMP_FILE"
cat "$CRM_CADDY_FRAGMENT" >> "$TEMP_FILE"
docker cp "$TEMP_FILE" "$CADDY_CONTAINER:/tmp/podoria-combined.Caddyfile"
docker exec "$CADDY_CONTAINER" \
  caddy validate --config /tmp/podoria-combined.Caddyfile >/dev/null
docker exec "$CADDY_CONTAINER" \
  caddy reload --config /tmp/podoria-combined.Caddyfile >/dev/null

printf '{"status":"reconciled","container":"%s","edge_network":"%s"}\n' \
  "$CADDY_CONTAINER" "$EDGE_NETWORK_NAME"
