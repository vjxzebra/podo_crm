FROM python:3.12.13-alpine3.23

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk upgrade --no-cache \
    && addgroup --system app \
    && adduser --system --ingroup app --home /app app

COPY requirements ./requirements
RUN python -m pip install -r requirements/dev.txt
RUN apk add --no-cache font-dejavu \
    && apk add --no-cache --virtual .python-rundeps-postgres-only \
      "so:libbz2.so.1" \
      musl \
      "so:libcrypto.so.3" \
      "so:libffi.so.8" \
      "so:libgdbm.so.6" \
      "so:libgdbm_compat.so.4" \
      "so:liblzma.so.5" \
      "so:libncursesw.so.6" \
      "so:libnsl.so.3" \
      "so:libpanelw.so.6" \
      "so:libreadline.so.8" \
      "so:libssl.so.3" \
      "so:libtirpc.so.3" \
      "so:libuuid.so.1" \
      "so:libz.so.1" \
    && apk del .python-rundeps sqlite-libs \
    && rm -rf \
      /usr/local/lib/python3.12/sqlite3 \
      /usr/local/lib/python3.12/lib-dynload/_sqlite3.*

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "/app/run-web.sh"]
