# Immich Companion

Immich Companion is an API-first operational workspace for Immich. It is being
built to provide advanced search, safe bulk actions, duplicate review, tagging,
integrity analysis, and people/album workflows without modifying Immich's
database or media files directly.

The current vertical slice includes a FastAPI service, a componentized Svelte
status dashboard and asset workspace, typed Immich asset/album synchronization,
nested PostgreSQL search with stable configurable ordering, image cards, and a
full-size fullscreen viewer. Checked, current-page, inverted-page, and
all-matching selections can be resolved by the backend and sent through a
reviewed bulk-action flow for multi-album/tag addition and removal, archive,
favorite, trash, and restore. The
reproducible integration environment is backed by real Immich v3.1.0 and seeds
66 unique images, producing three pages at the frontend's default 24-card size
and still a second page at the 48-card option. Production defaults remain safe:
trash is disabled unless `ALLOW_DESTRUCTIVE_ACTIONS` is explicitly enabled.

## Quick start

Requirements:

- Docker with either `docker compose` or `docker-compose` (the current Compose
  plugin is preferred by Immich)
- `curl` for the smoke check
- Python 3 for deterministic local configuration and media generation

Start or update the isolated test environment while preserving its databases,
Immich media, API key, and model cache:

```bash
./scripts/test-env.sh start
```

After the first successful bootstrap, ordinary `start` and `restart` preserve
the existing Immich instance without rerunning fixture reconciliation. They may
rebuild the companion image and refresh only the companion-owned asset index.
Use `start --reset` only when you explicitly want to delete the isolated test
volumes and recreate deterministic fixtures.

Open <http://localhost:8090> for the built companion dashboard,
<http://localhost:8090/assets> for search/cards/viewer, and
<http://localhost:22830> for Immich. Inspect the companion API with:

```bash
curl http://localhost:8090/api/health
curl http://localhost:8090/api/version
curl http://localhost:8090/api/capabilities
curl http://localhost:8090/api/test-state
curl http://localhost:8090/api/assets
```

The helper generates ignored local credentials in
`.local/test-environment/compose.env`. The Immich test administrator is
`companion-test@example.invalid`; inspect that local file when you need its
password for the Immich UI. The generated companion API key remains in an
isolated Docker volume and is never printed.

To intentionally discard both PostgreSQL databases, uploaded Immich media, the
generated API key, and the model cache, then recreate the same deterministic
seed:

```bash
./scripts/test-env.sh start --reset
```

Only volumes in the `immich-companion-test` Compose project are removed. Plain
`start`, `restart`, `stop`, and a later `start` preserve them.

Inspect or stop it without writing Compose commands manually:

```bash
./scripts/test-env.sh status
./scripts/test-env.sh logs
./scripts/test-env.sh stop
```

The helper refreshes the companion asset index through the Immich API after each
successful start, so the deterministic cards are immediately available. The
environment runs pinned Immich server, machine-learning, Valkey, and Immich
PostgreSQL services plus a separate PostgreSQL service owned by the companion.
Deterministic media is uploaded through the supported Immich API; the companion
does not mount Immich media or access Immich's database.

Synchronization is catalog-first and staged. Every run first reconciles the
complete album and tag catalogs, then processes image metadata in bounded
batches, followed by stacks and normalized album/tag memberships. A generation
is validated before stale relationships or catalog rows are removed; media rows
are removed only after a successful full traversal. Routine incremental runs use
the last successful watermark with an overlap window, while the confirmed Full
sync control scans all media. PostgreSQL stores the run, lease, cursor, counters,
and watermark, so syncs cannot overlap and progress remains visible after a page
reload or service restart.

The main tuning values are `SYNC_BATCH_SIZE` (default `250`),
`SYNC_OVERLAP_SECONDS` (default `300`), and `SYNC_LEASE_SECONDS` (default `60`).
Global sync load defaults to 50 assets per batch with a 0.2-second minimum pause;
configure these values from Settings. Each persisted full-sync batch then waits at
least that delay and otherwise as long as the preceding batch took, avoiding
sustained full-host pressure. Environment values seed a new companion database;
saved Settings values take precedence and survive restarts.
Automatic schedules are disabled by default and are configured from the Settings
page using common presets or five-field cron expressions. The default schedule
values are incremental every 15 minutes and full repair every Sunday at midnight;
retry settings remain environment-backed.
The asset page exposes an incremental control plus a confirmed administrator full
sync. API clients can start a run with `POST /api/assets/sync/start`, inspect the
coordinator with `GET /api/assets/sync/status`, and audit a specific persisted run
with `GET /api/assets/sync/runs/{run_id}`.

The seed includes exact-byte and pixel-identical variants, crops, edits,
occlusions, alpha images, aspect-ratio and dimension variants, negative controls,
overlapping albums, stacks, favorites, archived assets, and trashed assets. A
four-tag taxonomy is assigned across 48 assets with intentional overlap. A plain
start converges those fixtures without duplicating them; `--reset` proves the
same corpus and tag assignments can be recreated from empty volumes.

The asset page opens in Simple mode with filename, media-type, favorite,
archive, and trash filters; trashed assets are excluded by default. Its
collapsible Advanced zone adds taken-date, width/height, and aspect-ratio bounds.
Aspect-ratio fields accept decimals or fractions such as `16/9`; Expert equality
uses an explicit approximate match with a 0.1% relative tolerance. The Expert
switch exposes recursive AND/OR groups, whole-group NOT, and album
membership/exclusion. Results use a
four-column desktop grid and full numbered pagination with first/last
navigation, nearby-page windows, and 24/48/96/192 item page sizes. Cards use
thumbnails and expose album, tag, stack,
external-source, and Open in Immich indicators when their metadata is available.
Indicator popovers list relation details, and stack popovers preview their member
images. The dialog requests the original Immich asset and provides
fit/actual-size, wheel/button zoom,
collection navigation, selection, details, and shortcuts. Its reusable bottom
comparison strip defaults to stack members and click activation, while also
supporting future similar-image collections and hover or press-and-hold
comparison behavior.

The selection action bar appears only after selection begins and remains below
the sticky application header. The card media area then supports click,
Shift-range, and pointer-drag selection or deselection while retaining a
dedicated viewer button. Exact checked assets, the current page, page inversion,
or every backend-resolved match use the same reviewed action flow. Album and tag
actions use searchable multi-select dialogs; additions skip existing members
and removals skip missing memberships. Mixed selections show one dynamic
Archive/Unarchive direction and one Favorite/Unfavorite direction; Trash and
Restore remain independently available when either state applies. Shared typed
icons, icon-button legends, dialogs, and confirmation dialogs provide the
reusable UI foundation for these controls.

Search, Expert rules, and pagination share fully styled Svelte select controls.
Search date-times use the shared custom calendar and hour/minute picker rather
than browser-native select or date-time inputs.

## Fast frontend iteration against the integration environment

Keep Immich and the backend running in Docker, then launch only Vite in WSL:

```bash
./scripts/test-env.sh start
./scripts/test-env.sh frontend
```

Or start everything and enter the frontend loop in one command:

```bash
./scripts/test-env.sh start --frontend
```

Open <http://localhost:5173> from Windows. Vite binds to `0.0.0.0`, proxies
`/api` to the companion on port 8090, and applies Svelte/CSS changes with native
hot-module replacement. `Ctrl+C` stops Vite only; Immich and the backend keep
running. The helper installs locked frontend dependencies only when missing or
when the lockfile changed. Apply backend changes with another plain `start`,
which rebuilds containers while retaining environment state.

### Windows access when Docker runs inside WSL 2

The companion, Immich, and Vite ports bind to `0.0.0.0` inside WSL by default so
Windows can reach them. The helper prints localhost and WSL-IP fallback URLs.

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
may also make the test ports reachable from the local network, subject to WSL
and Windows firewall rules. For WSL-only access, set `COMPANION_TEST_BIND`,
`IMMICH_TEST_BIND`, and `COMPANION_FRONTEND_BIND` to `127.0.0.1` before starting
their processes.

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

When the backend runs without compiled frontend assets, `/` intentionally
returns a diagnostic 503 response. Run the Vite development server below for
the local UI. Vite targets the integration backend at `http://127.0.0.1:8090`
by default; set `VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000` when using the
standalone backend command above.

## Local frontend development

The frontend requires Node.js 22 or newer. Install its locked dependencies and
start Vite:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The dev server binds to `0.0.0.0` for
Windows-to-WSL access and reserves port
5173 with strict-port handling. Startup fails visibly instead of silently
opening Immich Companion on another port when 5173 is already occupied.

Run the deterministic frontend checks with:

```bash
npm run check
npm test
npm run build
npm run test:browser
```

The browser test uses a built preview and mocked read-only API responses by
default. To test an already-running companion test environment instead:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8090 \
PLAYWRIGHT_USE_LIVE_API=1 \
npm run test:browser
```

## Container image and production stack

The GitHub Actions workflow builds the same image used by the test environment
and publishes it to `ghcr.io/desapoint/immich-companion`. A minimal Compose
overlay for the existing Immich stack is in
[`deploy/compose.companion.yml`](deploy/compose.companion.yml), with deployment
notes in [`deploy/README.md`](deploy/README.md).

The companion image is safe to add alongside the existing services, but it does
not yet replace the current tagger or deduper. Those services should be disabled
only after their corresponding parity tasks have passed staging validation.

## Safety boundaries

- Immich API is the normal integration boundary.
- Direct writes to the Immich database are forbidden.
- Direct mutation of Immich-managed media files is forbidden.
- Companion-owned state uses a database separate from the Immich application DB.
- Destructive operations use plan, review, execute, and verify stages.
- Qdrant is reserved for vectors; it is not required by the bootstrap.
- No LLM is required by the project.

## Roadmap

The detailed task graph is maintained locally in the ignored `TASKS.md` file.
The implementation guide and imported reference scripts remain local under the
ignored `docs/` directory.
