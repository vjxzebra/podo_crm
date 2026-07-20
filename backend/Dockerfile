FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY requirements ./requirements
RUN python -m pip install -r requirements/dev.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "/app/run-web.sh"]
