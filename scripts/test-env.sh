#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_DIR}/docker/compose.test.yml"
PROJECT_NAME="immich-companion-test"
TEST_PORT="${COMPANION_TEST_PORT:-8090}"
BASE_URL="http://127.0.0.1:${TEST_PORT}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required (docker compose or docker-compose)." >&2
  exit 1
fi

compose() {
  "${COMPOSE[@]}" --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" "$@"
}

smoke() {
  local health
  health="$(curl --fail --silent --show-error "${BASE_URL}/api/health")"
  if [[ "${health}" != *'"ready":true'* && "${health}" != *'"ready": true'* ]]; then
    echo "Companion responded but is not ready: ${health}" >&2
    return 1
  fi
  curl --fail --silent --show-error "${BASE_URL}/api/capabilities" >/dev/null
  echo "Smoke check passed: ${BASE_URL}"
}

wait_until_ready() {
  local attempt
  for attempt in {1..45}; do
    if smoke >/dev/null 2>&1; then
      smoke
      return 0
    fi
    sleep 1
  done
  echo "Companion did not become ready within 45 seconds." >&2
  compose logs --tail=100
  return 1
}

show_access_urls() {
  echo "WSL/Linux URL: ${BASE_URL}"
  if grep --quiet --ignore-case microsoft /proc/version 2>/dev/null; then
    local wsl_ip
    wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "Windows URL: http://localhost:${TEST_PORT}"
    if [[ -n "${wsl_ip}" ]]; then
      echo "Windows fallback: http://${wsl_ip}:${TEST_PORT}"
    fi
  fi
}

start_environment() {
  # The test stack is intentionally stateless. Removing stale containers first
  # also avoids docker-compose 1.29's ContainerConfig recreation failure with
  # current Docker Engine releases.
  compose down --remove-orphans
  compose up --detach --build
  wait_until_ready
  show_access_urls
}

usage() {
  echo "Usage: $0 {start|stop|restart|status|logs|smoke|config}"
}

case "${1:-}" in
  start)
    start_environment
    ;;
  stop)
    compose down --remove-orphans
    ;;
  restart)
    start_environment
    ;;
  status)
    compose ps
    ;;
  logs)
    compose logs --tail=200
    ;;
  smoke)
    smoke
    ;;
  config)
    compose config
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
