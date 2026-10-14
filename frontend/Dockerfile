# BilimUz Frontend — PRODUCTION image (build + serve).
#
# No frontend Dockerfile existed before this sprint (confirmed: `find
# frontend -maxdepth 1 -iname "Dockerfile*"` returned nothing). This one
# builds the Vite app and serves the static output through nginx, which
# also reverse-proxies /api/v1/ to the backend — see nginx/nginx.conf's
# own header comment for why same-origin matters for this app's cookies.
#
# IMPORTANT — build context must be the REPOSITORY ROOT, not frontend/,
# because this file also needs nginx/nginx.conf. docker-compose.prod.yml
# is already set up this way (`context: .`, `dockerfile: frontend/
# Dockerfile`). A manual `docker build` must do the same:
#   docker build -f frontend/Dockerfile -t bilimuz-frontend:latest .

# ---- Stage 1: build the Vite app --------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

# Vite inlines VITE_* variables into the built JS at BUILD time, not at
# container-start time — there is no "runtime env var" for a static
# build. Defaults to "/api/v1" (a path, no host) so the built app calls
# the SAME origin it's served from and nginx's /api/v1/ proxy handles
# routing to the backend — the architecture this whole deployment is
# built around (see nginx/nginx.conf). Override at build time only if
# you have a real reason to point a build at a different API host:
#   docker build --build-arg VITE_API_BASE_URL=/api/v1 -f frontend/Dockerfile -t bilimuz-frontend .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---- Stage 2: serve with nginx -----------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/healthz || exit 1

# nginx:alpine's own image already runs its master process as root (by
# design, to bind port 80/443) with worker processes dropped to an
# unprivileged user internally — this is the image's documented,
# standard behavior, not something this Dockerfile needs to override.
