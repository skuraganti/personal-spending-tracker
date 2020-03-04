#!/bin/sh
# Select only this portfolio stack; preserve all unrelated containers and volumes.
set -eu
cd "$(dirname "$0")/.."
if command -v docker-compose >/dev/null 2>&1; then
  case "${1:-up}" in
    up) exec docker-compose up -d --build ;;
    stop) exec docker-compose stop ;;
    logs) exec docker-compose logs --tail=100 app ;;
    status) exec docker-compose ps ;;
    *) echo "Usage: sh scripts/stack.sh [up|stop|logs|status]" >&2; exit 2 ;;
  esac
else
  case "${1:-up}" in
    up) exec docker compose up -d --build ;;
    stop) exec docker compose stop ;;
    logs) exec docker compose logs --tail=100 app ;;
    status) exec docker compose ps ;;
    *) echo "Usage: sh scripts/stack.sh [up|stop|logs|status]" >&2; exit 2 ;;
  esac
fi
