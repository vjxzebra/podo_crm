#!/bin/sh
set -eu

ruff check .
ruff format --check .
mypy --no-sqlite-cache
python manage.py check
python manage.py migrate --noinput
python manage.py migrate --check
pytest
python manage.py spectacular \
  --file /tmp/podoria-openapi.json \
  --format openapi-json \
  --validate
python scripts/check_openapi_snapshot.py /tmp/podoria-openapi.json openapi/schema.json
