#!/bin/sh
set -eu

python manage.py migrate --noinput

if [ "${DJANGO_DEBUG:-0}" = "1" ]; then
  exec python manage.py runserver 0.0.0.0:8000
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_CONCURRENCY:-2}" --timeout 60
