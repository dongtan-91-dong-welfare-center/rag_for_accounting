#!/usr/bin/env bash
# Build and run the containerized stack:
# - database: PostgreSQL + pgvector
# - embedding: TEI serving nlpai-lab/KURE-v1
# - app: FastAPI API + built React frontend on port 8000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for tool in docker curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool" >&2; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "Docker daemon is not running." >&2; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env was created from .env.example. Fill OPENAI_API_KEY, then rerun ./install.sh." >&2
  exit 1
fi

echo "[1/3] Building and starting containers"
docker compose up -d --build

echo "[2/3] Waiting for app server"
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:8000/health >/dev/null 2>&1 \
  || { echo "app server is not ready. Check: docker compose logs app" >&2; exit 1; }

echo "[3/3] Stack is running"
echo "  App/API   : http://localhost:8000"
echo "  API docs  : http://localhost:8000/docs"
echo "  Embedding : http://localhost:8080"
echo "  DB        : localhost:5432"
echo
echo "Useful commands:"
echo "  ./check.sh"
echo "  docker compose logs -f app"
echo "  docker compose down"
