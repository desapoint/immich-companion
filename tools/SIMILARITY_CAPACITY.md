# Similarity candidate capacity harness

`profile_similarity_capacity.py` exercises the production Appearance candidate index using
deterministic metadata only. It never needs media originals, Immich access, a database, or a
Qdrant instance.

Run the current-library baseline from the repository root:

```bash
backend/.venv/bin/python tools/profile_similarity_capacity.py \
  --assets 60000 --pattern clustered
```

Use `--pattern collision` to stress a worst-case set where every asset has the same perceptual
hash. Saturated index entries are removed from consideration, so both the intermediate query
result and final graph remain bounded by `--maximum-neighbors`.

## 2026-09-09 baseline

Measured in the repository's Python 3.12 Companion image with eight neighbors and exact hash
lookup. RSS includes the approximately 90 MiB interpreter/application baseline.

| Assets | Pattern | Candidate pairs | Pair ceiling | Peak query matches | Peak RSS | Candidate time |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 60,000 | clustered | 239,991 | 240,000 | 8 | 173.2 MiB | 8.52 s |
| 60,000 | collision | 239,991 | 240,000 | 8 | 168.8 MiB | 6.30 s |
| 60,000 | sparse | 0 | 240,000 | 0 | 187.1 MiB | 4.97 s |
| 250,000 | collision | 999,993 | 1,000,000 | 8 | 424.4 MiB | 26.56 s |

The hard correctness checks performed by the harness are:

- candidate pair count is at most `assets * maximum_neighbors / 2`;
- observed degree never exceeds the configured neighbor maximum;
- candidate identities are canonical and deterministic through the production implementation;
- memory and elapsed-time samples are emitted before allocation, after synthetic feature
  creation, after candidate creation, and after references are released.

Each sample also records process user/system CPU time and kernel-reported disk read/write bytes.
The result explicitly reports external API and media-file reads, both of which remain zero for
this metadata-only capacity boundary.

The normal and collision runs make zero Immich/API requests and perform no database or media
I/O. This isolates the candidate-index cost. End-to-end image decode, persistent feature scan,
and future vector-index measurements remain separate stage gates because synthetic metadata
must not be mistaken for real-media validation.
