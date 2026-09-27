# Immich 3.2 API migration

Companion targets stable Immich 3.2.x. The compatibility report marks 3.1 and
other lines incompatible, and the isolated test stack pins v3.2.0.

## Search

Immich 3.2 selects its structured metadata search when a request includes
`filter`, `orderBy`, or `cursor`. Companion now uses these fields for active
inventory, trash, album membership, and tag membership. Active inventory uses
`trashedAt: {eq: null}`; trash uses `trashedAt: {ne: null}`. This explicitly
separates those inventories, since the new search implementation does not
exclude deleted assets by default. Updated time windows use `updatedAt` range
operators. Pagination follows `nextCursor`, and sync checkpoints persist the
cursor for fast resumption. Older page-only checkpoints can still resume by
replaying cursor pages to the saved page number.

The adapter also accepts a structured filter tree for callers that need
album-scoped searches, top-level AND with OR branches, and `any`/`all`/`none`
matching for album, tag, or person IDs. Immich 3.2's DTO allows a top-level
branch plus one `or` array of branches; it does not accept recursively nested
OR arrays. Companion passes these filters through and leaves validation to
Immich. This is an integration capability, not a new Companion search UI.

Source: [Immich 3.2 search DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/search.dto.ts),
[search service](https://github.com/immich-app/immich/blob/v3.2.0/server/src/services/search.service.ts),
and [query builder](https://github.com/immich-app/immich/blob/v3.2.0/server/src/utils/database.ts).

## Deprecation audit and other 3.2 features

The 3.2 API marks flat search fields and page-number pagination deprecated.
Those usages were migrated. The API also marks `PUT /assets` and
`PUT /stacks/{id}` deprecated; Companion now uses their `PATCH` equivalents.
Tag updates already use `PATCH /tags/{id}`. Immich hides these PATCH routes
from its generated OpenAPI spec, but its controller implements them. The
optional `/api/sync/capabilities` probe is a Companion extension and remains
safe when Immich returns 404.

The 3.2 release also adds asset file APIs, workflow tags, and cross-user people
improvements. Companion's current media reads and tag sync do not require
those endpoints. Adopting them would change media selection or automation
behavior, so they are separate product work rather than part of this API
compatibility migration.

Sources: [Immich 3.2 release notes](https://github.com/immich-app/immich/discussions/31408),
[asset controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/asset.controller.ts),
[stack controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/stack.controller.ts),
and [tag controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/tag.controller.ts).
