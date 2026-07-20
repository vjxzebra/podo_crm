#!/bin/sh
set -eu

docker compose build backend
docker compose run --rm --no-deps backend \
  python manage.py spectacular \
  --file /app/openapi/schema.json \
  --format openapi-json \
  --validate
docker compose --profile tools build frontend-tools
docker compose --profile tools run --rm --no-deps frontend-tools npm run generate:api
