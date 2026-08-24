# Immich Companion

Immich Companion is an API-first operational workspace for Immich. It is being
built to provide advanced search, safe bulk actions, duplicate review, tagging,
integrity analysis, and people/album workflows without modifying Immich's
database or media files directly.

The current bootstrap is intentionally small: a FastAPI service, dependency
health reporting, a mock Immich service, a container build, and an on-demand
test environment. Destructive actions are disabled.

## Quick start

Requirements:

- Docker with either `docker compose` or `docker-compose`
- `curl` for the smoke check

Start the isolated test environment:

```bash
./scripts/test-env.sh start
```

Open <http://localhost:8090> or inspect the API:

```bash
curl http://localhost:8090/api/health
curl http://localhost:8090/api/version
curl http://localhost:8090/api/capabilities
```

Inspect or stop it without writing Compose commands manually:

```bash
./scripts/test-env.sh status
./scripts/test-env.sh logs
./scripts/test-env.sh stop
```

The test environment is isolated under the Compose project name
`immich-companion-test`, does not connect to a real Immich instance, and is
recreated from a clean stateless container set on every `start`.

### Windows access when Docker runs inside WSL 2

The test port binds to `0.0.0.0` inside WSL by default so Windows can reach it.
After `start`, the helper prints both:

- `http://localhost:8090`
- a fallback URL using the current WSL virtual-machine IP

Use plain `http://`, not `https://`. If Windows localhost forwarding is disabled,
create or update `%UserProfile%\.wslconfig` from Windows with:

```ini
[wsl2]
localhostForwarding=true
```

Then run `wsl --shutdown` in PowerShell and restart WSL. This stops all running
WSL distributions and containers. On Windows 11 22H2 or newer, mirrored
networking is another option:

```ini
[wsl2]
networkingMode=mirrored
```

Do not combine networking changes casually with a production Tailscale setup;
try the wildcard bind and printed WSL-IP fallback first. Binding to `0.0.0.0`
may also make the test port reachable from the local network, subject to WSL
and Windows firewall rules. To restore WSL-only access, export
`COMPANION_TEST_BIND=127.0.0.1` before starting.

## Local backend development

The project targets Python 3.12 or newer.

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev]'
backend/.venv/bin/uvicorn companion.main:app --app-dir backend --reload
```

Run the backend checks with:

```bash
backend/.venv/bin/pytest backend/tests
backend/.venv/bin/ruff check backend
```

## Container image and production stack

The GitHub Actions workflow builds the same image used by the test environment
and publishes it to `ghcr.io/desapoint/immich-companion`. A minimal Compose
overlay for the existing Immich stack is in
[`deploy/compose.companion.yml`](deploy/compose.companion.yml), with deployment
notes in [`deploy/README.md`](deploy/README.md).

The bootstrap image is safe to add alongside the existing services, but it does
not yet replace the current tagger or deduper. Those services should be disabled
only after their corresponding parity tasks have passed staging validation.

## Safety boundaries

- Immich API is the normal integration boundary.
- Direct writes to the Immich database are forbidden.
- Direct mutation of Immich-managed media files is forbidden.
- The future companion database is separate from the Immich application DB.
- Destructive operations use plan, review, execute, and verify stages.
- Qdrant is reserved for vectors; it is not required by the bootstrap.
- No LLM is required by the project.

## Roadmap

The detailed task graph is maintained locally in the ignored `TASKS.md` file.
The implementation guide and imported reference scripts remain local under the
ignored `docs/` directory.
