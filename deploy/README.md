# Production stack overlay

`compose.companion.yml` is an additive overlay for the existing Immich Compose
stack. It follows the current stack's `tailscale` service name and reaches
Immich at `http://tailscale:2283`, just like the existing booru tagger. It adds
no media mount and performs no direct database access.

## Add the bootstrap safely

1. Copy `compose.companion.yml` beside the production `compose.yaml`.
2. Set `COMPANION_IMMICH_API_KEY` through the stack's secret/environment
   management and optionally set `IMMICH_COMPANION_VERSION` to an immutable
   release or SHA tag.
3. Load the original file and the overlay together in the deployment UI or
   Compose command used by the host.
4. Confirm the companion reports `ready: true` before exposing port 8090 beyond
   a trusted network.

The only new service is `immich-companion`. Existing Immich, Tailscale,
PostgreSQL, Valkey, machine-learning, and power-tools definitions remain
unchanged.

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

## Companion database later

The bootstrap has no application database. When schema work lands, provision a
separate `immich_companion` database and least-privilege role on the existing
PostgreSQL server, then add only that connection to this overlay. Never point
the companion's application models at the `immich` database.
