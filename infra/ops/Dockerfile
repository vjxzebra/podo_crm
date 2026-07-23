FROM golang:1.26.5-alpine3.24 AS age-builder

ARG AGE_VERSION=v1.3.1

RUN apk add --no-cache git
RUN git clone --depth 1 --branch "${AGE_VERSION}" \
    https://github.com/FiloSottile/age.git /src/age
WORKDIR /src/age
RUN go get golang.org/x/crypto@v0.52.0 \
    && go mod tidy \
    && go test ./... \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/age ./cmd/age \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/age-keygen ./cmd/age-keygen

FROM python:3.14.6-alpine3.24

RUN apk add --no-cache \
    bash \
    coreutils \
    findutils \
    gzip \
    postgresql17-client \
    && python3 -m venv /opt/ops-venv \
    && /opt/ops-venv/bin/pip install --no-cache-dir minio==7.2.20

ENV PATH="/opt/ops-venv/bin:${PATH}"

COPY --from=age-builder /out/age /out/age-keygen /usr/local/bin/
COPY backup.sh restore.sh retention.sh ops-entrypoint json_ops.py minio_ops.py /usr/local/bin/
RUN chmod 0555 \
    /usr/local/bin/age \
    /usr/local/bin/age-keygen \
    /usr/local/bin/backup.sh \
    /usr/local/bin/restore.sh \
    /usr/local/bin/retention.sh \
    /usr/local/bin/ops-entrypoint \
    /usr/local/bin/json_ops.py \
    /usr/local/bin/minio_ops.py

ENTRYPOINT ["/usr/local/bin/ops-entrypoint"]
