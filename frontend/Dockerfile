FROM node:24.17.0-bookworm-slim AS dependencies

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS source

COPY frontend/ ./
COPY backend/openapi/schema.json ./openapi/schema.json

FROM source AS verified

RUN npm run check

FROM nginx:1.28.3-alpine AS runtime

RUN cp /etc/nginx/nginx.conf /tmp/nginx.conf.official \
    && apk del \
      nginx \
      nginx-module-acme \
      nginx-module-geoip \
      nginx-module-image-filter \
      nginx-module-njs \
      nginx-module-xslt \
    && apk add --no-cache nginx \
    && apk upgrade --no-cache \
    && cp /tmp/nginx.conf.official /etc/nginx/nginx.conf \
    && rm /tmp/nginx.conf.official

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=verified /app/dist /usr/share/nginx/html

EXPOSE 80
