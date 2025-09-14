#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "1/6 Checking Docker availability..."
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found in PATH"; exit 1
fi
if ! command -v docker-compose >/dev/null 2>&1; then
  echo "WARNING: docker-compose not found, trying 'docker compose'..."
  if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: neither docker-compose nor 'docker compose' available"; exit 1
  else
    DCMD="docker compose"
  fi
else
  DCMD="docker-compose"
fi

echo "2/6 Building and starting containers (detached)..."
$DCMD -f docker-compose.yml up --build -d

echo "3/6 Showing container status..."
$DCMD ps

echo "4/6 Waiting for services to start (10s)..."
sleep 10

APP_URL="http://localhost:5000/"

echo "5/6 Checking HTTP endpoint: $APP_URL"
if command -v curl >/dev/null 2>&1; then
  if curl -sS --max-time 5 -I "$APP_URL" | head -n 1 | grep -E "HTTP/|HTTP " >/dev/null 2>&1; then
    curl -sS -I "$APP_URL" | head -n 5
    echo "HTTP check: OK"
  else
    echo "HTTP check: no response (check container logs)"
  fi
else
  echo "curl not installed; open $APP_URL in a browser to check."
fi

echo "6/6 Recent logs (tail 200):"
$DCMD logs --tail=200

echo "Done. If something failed, paste the logs shown above and I will help debug."
