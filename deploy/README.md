# Production stack overlay

`compose.companion.yml` is an additive overlay for the existing Immich Compose
stack. It follows the current stack's `tailscale` service name and reaches
Immich at `http://tailscale:2283`, just like the existing booru tagger. It adds
no media mount and performs no direct database access.

## Add the bootstrap safely

1. Copy `compose.companion.yml` beside the production `compose.yaml`.
2. Set `COMPANION_IMMICH_API_KEY` through the stack's secret/environment
   management, set a strong `IMMICH_COMPANION_DB_PASSWORD`, set
   `IMMICH_COMPANION_PUBLIC_IMMICH_URL` to the URL browsers use for Immich, and
   optionally set `IMMICH_COMPANION_VERSION` to an immutable release or SHA tag.
   Keep `ALLOW_DESTRUCTIVE_ACTIONS=false` until trash workflows have been
   validated in staging. `ACTION_MAX_TARGETS` and `ACTION_PLAN_TTL_SECONDS`
   bound action size and review lifetime. `IMMICH_COMPANION_SYNC_BATCH_SIZE`,
   `IMMICH_COMPANION_SYNC_OVERLAP_SECONDS`, and
   `IMMICH_COMPANION_SYNC_LEASE_SECONDS` map to the companion's staged sync
   batch size, overlap window, and coordinator lease duration. New companion
   databases seed Global sync load with
   `IMMICH_COMPANION_SYNC_FULL_BATCH_SIZE` (50) and
   `IMMICH_COMPANION_SYNC_FULL_MIN_BATCH_DELAY_SECONDS` (0.2); saved Settings
   values take precedence after initialization.
3. Load the original file and the overlay together in the deployment UI or
   Compose command used by the host.
4. Confirm the companion reports `ready: true` before exposing port 8090 beyond
   a trusted network.

If the dashboard is served through HTTPS, terminate TLS at the reverse proxy
and forward WebSocket upgrades for `/api/tasks/*/stream`. The browser derives
`wss://` automatically from the HTTPS dashboard URL; do not rewrite that
connection to plain `ws://`. The proxy must preserve the external `Host`
header so the companion's same-origin WebSocket check remains valid.

The overlay adds `immich-companion` and its isolated `immich-companion-database`.
Existing Immich, Tailscale, Immich PostgreSQL, Valkey, machine-learning, and
power-tools definitions remain unchanged. Alembic upgrades the isolated schema
when the companion starts.

## Replacing old services

The bootstrap does not yet replace any current feature service. Keep
`booru-tagger`, `immich-deduper`, and `immich-deduper-qdrant` enabled today.

Later, make the production change narrowly:

- Disable `immich-deduper` only after exact-dedupe and similarity parity is
  proven on staging.
- Disable `immich-deduper-qdrant` only after its data is no longer needed or the
  companion's vector migration has been validated.
- Disable `booru-tagger` only after ONNX tagging parity, scheduler behavior,
  model/config state, and API-applied tags are validated.
- Do not disable `immich-server`, `immich-machine-learning`, `database`,
  `redis`, or `tailscale`; they remain platform dependencies.

This preserves the requested production migration shape: add the companion,
then turn off only a service whose behavior has actually been replaced.

## Companion database

The overlay provisions a dedicated PostgreSQL service and volume for companion
metadata, search indexes, and future jobs. It is intentionally separate from
Immich's PostgreSQL service. Never point `COMPANION_DATABASE_URL` at the `immich`
database. Operators who already provision databases externally may replace only
the overlay database service and connection URL while preserving that boundary.
