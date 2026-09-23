#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing go-task..."
sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin

echo "==> Installing templ..."
go install github.com/a-h/templ/cmd/templ@latest

echo "==> Installing golangci-lint..."
curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh | sh -s -- -b /usr/local/bin

echo "==> Installing frontend dependencies..."
if [ -d "web-app" ] && [ -f "web-app/package.json" ]; then
    cd web-app && npm ci --no-audit --no-fund && cd ..
fi

echo "==> Downloading Go module dependencies..."
go mod download

echo "==> Setup complete!"
