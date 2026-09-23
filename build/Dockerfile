# ─── Stage 1: Build frontend ────────────────────────────────
FROM node:22-alpine AS frontend

WORKDIR /app/web-app

COPY web-app/package.json web-app/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web-app/ ./
RUN npm run build

# ─── Stage 2: Build Go binary ───────────────────────────────
FROM golang:1.26-alpine AS builder

RUN apk add --no-cache ca-certificates tzdata git curl

WORKDIR /app

# Cache Go module downloads
COPY go.mod go.sum ./
RUN go mod download

# Install templ CLI via pre-built binary
RUN curl -sSL https://github.com/a-h/templ/releases/download/v0.3.1020/templ_Linux_x86_64.tar.gz | tar -xz -C /usr/local/bin templ

COPY . .

# Generate Templ Go code
RUN templ generate

# Build static binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -buildvcs=false \
    -ldflags="-s -w" \
    -o /app/server \
    ./cmd/server/

# ─── Stage 3: Minimal runtime ───────────────────────────────
FROM scratch

# SSL certificates for HTTPS requests
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Timezone data
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Binary
COPY --from=builder /app/server /server

# Static assets (frontend SPA)
COPY --from=frontend /app/web-app/dist /web-app/dist

ENV STATIC_DIR=/web-app/dist
ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["/server"]
