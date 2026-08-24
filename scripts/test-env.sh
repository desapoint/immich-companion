#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_DIR}/docker/compose.test.yml"
PROJECT_NAME="immich-companion-test"
LOCAL_STATE_DIR="${REPO_DIR}/.local/test-environment"
COMPOSE_ENV_FILE="${LOCAL_STATE_DIR}/compose.env"
SEED_DIR="${REPO_DIR}/generated_dataset/immich-seed"
TEST_PORT="${COMPANION_TEST_PORT:-8090}"
BASE_URL="http://127.0.0.1:${TEST_PORT}"
IMMICH_PORT="${IMMICH_TEST_PORT:-22830}"
IMMICH_BASE_URL="http://127.0.0.1:${IMMICH_PORT}"
FRONTEND_PORT="${COMPANION_FRONTEND_PORT:-5173}"
FRONTEND_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}"

ensure_local_config() {
  python3 "${REPO_DIR}/tools/create_test_environment_config.py" \
    --output "${COMPOSE_ENV_FILE}"
}

rotate_local_config() {
  python3 "${REPO_DIR}/tools/create_test_environment_config.py" \
    --output "${COMPOSE_ENV_FILE}" \
    --force
}

ensure_local_config

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required (docker compose or docker-compose)." >&2
  exit 1
fi

compose() {
  "${COMPOSE[@]}" \
    --env-file "${COMPOSE_ENV_FILE}" \
    --project-name "${PROJECT_NAME}" \
    --file "${COMPOSE_FILE}" \
    "$@"
}

smoke() {
  local health state
  health="$(curl --fail --silent --show-error "${BASE_URL}/api/health")"
  if [[ "${health}" != *'"ready":true'* && "${health}" != *'"ready": true'* ]]; then
    echo "Companion responded but is not ready: ${health}" >&2
    return 1
  fi

  state="$(curl --fail --silent --show-error "${BASE_URL}/api/test-state")"
  if [[ "${state}" != *'"ready":true'* && "${state}" != *'"ready": true'* ]]; then
    echo "Deterministic Immich seed is not ready: ${state}" >&2
    return 1
  fi

  curl --fail --silent --show-error "${IMMICH_BASE_URL}/api/server/ping" >/dev/null
  compose exec -T database pg_isready --dbname=immich --username=postgres >/dev/null
  compose exec -T companion-database \
    pg_isready --dbname=immich_companion --username=companion >/dev/null
  curl --fail --silent --show-error "${BASE_URL}/api/capabilities" >/dev/null
  curl --fail --silent --show-error "${BASE_URL}/api/assets?page_size=1" >/dev/null
  echo "Smoke check passed: companion, real Immich, both PostgreSQL services, migrations, and seed state"
}

sync_companion_assets() {
  local result
  result="$(curl --fail --silent --show-error --request POST "${BASE_URL}/api/assets/sync")"
  echo "Companion asset index refreshed: ${result}"
}

wait_until_ready() {
  local attempt
  for attempt in {1..120}; do
    if smoke >/dev/null 2>&1; then
      smoke
      return 0
    fi
    sleep 1
  done
  echo "Companion did not become ready within 120 seconds." >&2
  compose logs --tail=100
  return 1
}

wait_for_immich() {
  local attempt
  for attempt in {1..120}; do
    if curl --fail --silent --show-error "${IMMICH_BASE_URL}/api/server/ping" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Immich did not become ready within 240 seconds." >&2
  compose logs --tail=100 immich-server database redis
  return 1
}

show_access_urls() {
  echo "Companion URL: ${BASE_URL}"
  echo "Immich URL: ${IMMICH_BASE_URL}"
  if grep --quiet --ignore-case microsoft /proc/version 2>/dev/null; then
    local wsl_ip
    wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "Windows companion URL: http://localhost:${TEST_PORT}"
    echo "Windows Immich URL: http://localhost:${IMMICH_PORT}"
    if [[ -n "${wsl_ip}" ]]; then
      echo "Windows companion fallback: http://${wsl_ip}:${TEST_PORT}"
      echo "Windows Immich fallback: http://${wsl_ip}:${IMMICH_PORT}"
    fi
  fi
}

generate_seed() {
  python3 "${REPO_DIR}/tools/generate_test_media.py" --output "${SEED_DIR}"
}

start_environment() {
  local reset_mode="${1:-false}"

  if [[ "${reset_mode}" == "true" ]]; then
    echo "Resetting only the isolated ${PROJECT_NAME} containers and volumes..."
    compose down --volumes --remove-orphans
    rotate_local_config
  else
    # Recreate containers to avoid legacy docker-compose recreation bugs while
    # deliberately retaining all named volumes and database/media state.
    compose down --remove-orphans
  fi

  generate_seed
  compose build companion
  compose up --detach database redis immich-machine-learning immich-server companion-database
  wait_for_immich
  COMPANION_TEST_RESET_MODE="${reset_mode}" compose run --rm --no-deps immich-bootstrap
  compose up --detach companion
  wait_until_ready
  sync_companion_assets
  show_access_urls
}

show_frontend_urls() {
  echo "Frontend HMR URL: ${FRONTEND_BASE_URL}"
  if grep --quiet --ignore-case microsoft /proc/version 2>/dev/null; then
    local wsl_ip
    wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "Windows frontend URL: http://localhost:${FRONTEND_PORT}"
    if [[ -n "${wsl_ip}" ]]; then
      echo "Windows frontend fallback: http://${wsl_ip}:${FRONTEND_PORT}"
    fi
  fi
}

start_frontend() {
  if ! smoke >/dev/null 2>&1; then
    echo "Start the integration environment before launching the frontend: $0 start" >&2
    return 1
  fi

  if [[ ! -f "${REPO_DIR}/frontend/node_modules/.package-lock.json" || \
        "${REPO_DIR}/frontend/package-lock.json" -nt "${REPO_DIR}/frontend/node_modules/.package-lock.json" ]]; then
    npm --prefix "${REPO_DIR}/frontend" ci
  fi

  show_frontend_urls
  echo "Vite is proxying /api to ${BASE_URL}; Ctrl+C stops only Vite."
  VITE_BACKEND_PROXY_TARGET="${BASE_URL}" \
    npm --prefix "${REPO_DIR}/frontend" run dev -- \
      --host "${COMPANION_FRONTEND_BIND:-0.0.0.0}" \
      --port "${FRONTEND_PORT}" \
      --strictPort
}

parse_start_options() {
  RESET_MODE=false
  START_FRONTEND=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --reset)
        RESET_MODE=true
        ;;
      --frontend)
        START_FRONTEND=true
        ;;
      *)
        echo "Unknown start option: $1" >&2
        usage >&2
        exit 2
        ;;
    esac
    shift
  done
}

usage() {
  echo "Usage: $0 start [--reset] [--frontend]"
  echo "       $0 {frontend|stop|restart|status|logs|smoke|config}"
}

COMMAND="${1:-}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "${COMMAND}" in
  start)
    parse_start_options "$@"
    start_environment "${RESET_MODE}"
    if [[ "${START_FRONTEND}" == "true" ]]; then
      start_frontend
    fi
    ;;
  stop)
    if [[ $# -ne 0 ]]; then
      usage >&2
      exit 2
    fi
    compose down --remove-orphans
    echo "Stopped containers; test databases and media volumes were preserved."
    ;;
  restart)
    parse_start_options "$@"
    start_environment "${RESET_MODE}"
    if [[ "${START_FRONTEND}" == "true" ]]; then
      start_frontend
    fi
    ;;
  frontend)
    if [[ $# -ne 0 ]]; then
      usage >&2
      exit 2
    fi
    start_frontend
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
    compose config --quiet
    echo "Compose configuration is valid."
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
