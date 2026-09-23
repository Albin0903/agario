---
name: deploy-docker
description: >
  Gère les builds Docker multi-stage vers scratch et les tests de conteneur.
  Utiliser pour toute tâche de packaging, de Dockerfile, ou de déploiement.
allowed-tools: Bash, Read, Write
---

# Docker Scratch — Conventions de Packaging

## Principe

Chaque image de production est construite en multi-stage et cible exclusivement `scratch` comme image finale.

## Structure du Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:22-alpine AS frontend
WORKDIR /app/web-app
COPY web-app/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web-app/ ./
RUN npm run build

# Stage 2: Build Go binary
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
COPY --from=frontend /app/web-app/dist ./web-app/dist
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w" -o /app/server ./cmd/server/

# Stage 3: Scratch runtime
FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /app/server /server
COPY --from=builder /app/web-app/dist /static/dist
EXPOSE 8080
ENTRYPOINT ["/server"]
```

## Règles impératives

1. **Image finale = `scratch`** : Aucune exception. Pas d'Alpine, pas de Debian.
2. **Binaire statique** : `CGO_ENABLED=0` obligatoire.
3. **Flags de linking** : `-ldflags="-s -w"` pour réduire la taille (supprime symboles et DWARF).
4. **Certificats SSL** : Toujours copier `/etc/ssl/certs/ca-certificates.crt`.
5. **Timezone** : Copier `/usr/share/zoneinfo` si l'application gère des dates localisées.
6. **User non-root** : Dans l'image `scratch`, le binaire tourne en PID 1 (acceptable car aucun shell disponible).

## Validation

```bash
# Build et vérification de la taille
docker build -t app:latest -f build/Dockerfile .
docker images app:latest --format '{{.Size}}'
# Attendu : 15-25 Mo

# Test de démarrage
docker run --rm -p 8080:8080 app:latest &
curl -s http://localhost:8080/api/health | jq .
```

## Anti-patterns

- ❌ `FROM alpine` en stage final
- ❌ `CGO_ENABLED=1` en production
- ❌ Oublier les certificats SSL (cause: `x509: certificate signed by unknown authority`)
- ❌ Copier le code source dans l'image finale
