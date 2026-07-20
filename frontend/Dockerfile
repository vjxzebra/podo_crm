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

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=verified /app/dist /usr/share/nginx/html

EXPOSE 80
