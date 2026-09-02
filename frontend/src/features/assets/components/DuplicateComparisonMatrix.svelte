<script lang="ts">
  import { assetMediaUrl } from '../api/assetApi';
  import type { DuplicateReviewContext, DuplicateReviewMember } from '../types/assets';

  interface Props {
    context: DuplicateReviewContext;
    referenceId: string;
    visibleId: string;
  }

  let { context, referenceId, visibleId }: Props = $props();

  interface ComparisonRow {
    label: string;
    values: Array<{ id: string; value: string }>;
  }

  interface MemberVerdict {
    id: string;
    filename: string;
    verdict: string;
  }

  let overlayOpen = $state(false);
  let overlayOpacity = $state(50);
  const referenceMember = $derived(context.members.find((member) => member.id === referenceId) ?? null);
  const visibleMember = $derived(context.members.find((member) => member.id === visibleId) ?? null);

  function formatBytes(value: number | null): string {
    if (value === null) return 'Unavailable';
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }

  function shortHash(value: string | null | undefined): string {
    if (!value) return 'Unavailable';
    return value.length > 14 ? `${value.slice(0, 7)}…${value.slice(-6)}` : value;
  }

  function verdictFor(member: DuplicateReviewMember, reference: DuplicateReviewMember | null): string {
    if (!reference || member.id === reference.id) return 'Pinned comparison reference';
    if (member.is_offline) return 'Offline · visual and file validation may be incomplete';

    const current = member.preservation;
    const baseline = reference.preservation;
    if (!current || !baseline) {
      if (member.similarity?.exact_pixel_match) return 'Decoded pixels reported exact · preservation details unavailable';
      if (member.similarity?.state === 'current') return `Visual similarity ${member.similarity.similarity_percent?.toFixed(2) ?? '?'}% · needs manual validation`;
      return 'Needs manual validation · preservation data unavailable';
    }

    const samePixels = current.pixel_sha256 === baseline.pixel_sha256;
    const sameDimensions = current.decoded_width === baseline.decoded_width
      && current.decoded_height === baseline.decoded_height;

    if (!samePixels) {
      if (!sameDimensions) return 'Visual differences · decoded dimensions or crop differ';
      if (member.similarity?.exact_pixel_match === false) return 'Visual differences · normalized decoded pixels differ';
      return 'Visual differences detected';
    }

    const metadataDelta = current.metadata_richness - baseline.metadata_richness;
    if (metadataDelta > 0) return `Same pixels · richer metadata (+${metadataDelta})`;
    if (metadataDelta < 0) return `Same pixels · poorer metadata (${metadataDelta})`;

    const metadataSignals = [
      current.icc_profile_present === baseline.icc_profile_present,
      current.has_capture_time === baseline.has_capture_time,
      current.has_camera_info === baseline.has_camera_info,
      current.has_gps === baseline.has_gps,
      current.orientation === baseline.orientation,
    ];
    if (metadataSignals.some((matches) => !matches)) return 'Same pixels · metadata contents differ';

    if (member.file_size_bytes !== null && reference.file_size_bytes !== null) {
      if (member.file_size_bytes < reference.file_size_bytes) return 'Same pixels · metadata equivalent · smaller file';
      if (member.file_size_bytes > reference.file_size_bytes) return 'Same pixels · metadata equivalent · larger file';
    }
    return 'Same pixels · metadata equivalent';
  }

  const rowDefinitions: Array<{
    label: string;
    value: (member: DuplicateReviewMember) => string;
  }> = [
    { label: 'File size', value: (member) => formatBytes(member.file_size_bytes) },
    { label: 'Source', value: (member) => member.source_kind === 'upload' ? 'Immich upload' : `External · ${member.library_id ?? 'unknown'}` },
    { label: 'Availability', value: (member) => member.is_offline ? 'Offline' : 'Available' },
    { label: 'Existing stack', value: (member) => member.is_stacked ? 'Already stacked' : 'None' },
    { label: 'File content', value: (member) => shortHash(member.content_checksum) },
    { label: 'Normalized pixels', value: (member) => shortHash(member.preservation?.pixel_sha256) },
    { label: 'Decoded dimensions', value: (member) => member.preservation ? `${member.preservation.decoded_width}×${member.preservation.decoded_height}` : 'Unavailable' },
    { label: 'Bit depth / channels', value: (member) => member.preservation ? `${member.preservation.bit_depth}-bit · ${member.preservation.channel_count} ch` : 'Unavailable' },
    { label: 'Color / alpha', value: (member) => member.preservation ? `${member.preservation.color_space} · ${member.preservation.has_alpha ? 'alpha' : 'opaque'}` : 'Unavailable' },
    { label: 'ICC profile', value: (member) => member.preservation ? member.preservation.icc_profile_present ? 'Present' : 'Missing' : 'Unavailable' },
    { label: 'Orientation', value: (member) => member.preservation ? member.preservation.orientation === null ? 'None' : String(member.preservation.orientation) : 'Unavailable' },
    { label: 'Capture time', value: (member) => member.preservation ? member.preservation.has_capture_time ? 'Present' : 'Missing' : 'Unavailable' },
    { label: 'Camera metadata', value: (member) => member.preservation ? member.preservation.has_camera_info ? 'Present' : 'Missing' : 'Unavailable' },
    { label: 'GPS', value: (member) => member.preservation ? member.preservation.has_gps ? 'Present' : 'Missing' : 'Unavailable' },
    { label: 'Metadata richness', value: (member) => member.preservation ? `${member.preservation.metadata_richness}/6` : 'Unavailable' },
  ];

  const rows = $derived.by<ComparisonRow[]>(() => rowDefinitions
    .map((definition) => ({
      label: definition.label,
      values: context.members.map((member) => ({
        id: member.id,
        value: definition.value(member),
      })),
    }))
    .filter((row) => new Set(row.values.map((entry) => entry.value)).size > 1));

  const verdicts = $derived.by<MemberVerdict[]>(() => {
    const reference = context.members.find((member) => member.id === referenceId) ?? null;
    return context.members.map((member) => ({
      id: member.id,
      filename: member.filename,
      verdict: verdictFor(member, reference),
    }));
  });
</script>

<details class="comparison-matrix">
  <summary>
    <span>Group differences</span>
    <strong>{rows.length} differing {rows.length === 1 ? 'property' : 'properties'}</strong>
  </summary>

  <div class="visual-tools">
    <button type="button" disabled={!referenceMember || !visibleMember || referenceId === visibleId} onclick={() => overlayOpen = true}>Overlay reference / viewing</button>
    <small>Hold F in the viewer for rapid flicker comparison.</small>
  </div>

  <div class="verdicts" aria-label="Duplicate comparison summary">
    {#each verdicts as item (item.id)}
      <div class:reference={item.id === referenceId} class:viewing={item.id === visibleId}>
        <strong title={item.filename}>{item.filename}</strong>
        <span>{item.verdict}</span>
      </div>
    {/each}
  </div>

  {#if rows.length}
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Property</th>
            {#each context.members as member (member.id)}
              <th class:reference={member.id === referenceId} class:viewing={member.id === visibleId}>
                <span title={member.filename}>{member.filename}</span>
                <small>{member.id === referenceId ? 'Reference' : member.id === visibleId ? 'Viewing' : ''}</small>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.label)}
            <tr>
              <th>{row.label}</th>
              {#each row.values as entry (entry.id)}
                <td class:reference={entry.id === referenceId} class:viewing={entry.id === visibleId}>{entry.value}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p>All available comparison properties match across this group.</p>
  {/if}
</details>

{#if overlayOpen && referenceMember && visibleMember}
  <section class="overlay-view" role="dialog" aria-modal="true" aria-label="Reference overlay comparison">
    <header>
      <div>
        <strong>{referenceMember.filename}</strong>
        <span>Reference</span>
      </div>
      <div>
        <strong>{visibleMember.filename}</strong>
        <span>Viewing · {overlayOpacity}% opacity</span>
      </div>
      <label>
        <span>Viewing opacity</span>
        <input type="range" min="0" max="100" step="1" bind:value={overlayOpacity} />
      </label>
      <button type="button" onclick={() => overlayOpen = false}>Close overlay</button>
    </header>
    <div class="overlay-stage">
      <img src={assetMediaUrl(referenceId, 'fullsize')} alt={referenceMember.filename} draggable="false" />
      <img class="comparison-layer" src={assetMediaUrl(visibleId, 'fullsize')} alt={visibleMember.filename} draggable="false" style={`opacity: ${overlayOpacity / 100};`} />
    </div>
  </section>
{/if}

<style>
  .comparison-matrix {
    position: absolute;
    z-index: 6;
    top: .75rem;
    left: .75rem;
    width: min(46rem, calc(100% - 2.25rem));
    max-height: min(48vh, 30rem);
    overflow: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: color-mix(in srgb, var(--color-surface-raised) 96%, transparent);
    box-shadow: 0 .8rem 2.4rem rgb(0 0 0 / 30%);
    backdrop-filter: blur(.65rem);
  }

  summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .75rem;
    padding: .55rem .7rem;
    cursor: pointer;
    list-style: none;
    font-size: .66rem;
  }

  summary::-webkit-details-marker { display: none; }
  summary span { color: var(--color-accent-strong); font-weight: 820; text-transform: uppercase; }
  summary strong { color: var(--color-ink-muted); font-size: .6rem; }
  .visual-tools { display: flex; align-items: center; gap: .5rem; padding: .45rem .55rem; border-top: 1px solid var(--color-border-subtle); }
  .visual-tools button { min-height: 2rem; padding: .35rem .55rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); cursor: pointer; font: inherit; font-size: .6rem; font-weight: 760; }
  .visual-tools button:disabled { cursor: default; opacity: .45; }
  .visual-tools small { color: var(--color-ink-muted); font-size: .56rem; }
  .verdicts { display: grid; gap: .28rem; max-height: 8.5rem; padding: .45rem .55rem; overflow: auto; border-top: 1px solid var(--color-border-subtle); }
  .verdicts > div { display: grid; grid-template-columns: minmax(8rem, .42fr) minmax(0, 1fr); gap: .55rem; padding: .32rem .4rem; border-radius: var(--radius-sm); font-size: .6rem; }
  .verdicts strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .verdicts span { color: var(--color-ink-muted); }
  .table-scroll { max-height: calc(min(48vh, 30rem) - 14rem); overflow: auto; border-top: 1px solid var(--color-border-subtle); }
  table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: .6rem; }
  th, td { min-width: 8.25rem; max-width: 12rem; padding: .42rem .5rem; border-right: 1px solid var(--color-border-subtle); border-bottom: 1px solid var(--color-border-subtle); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
  th:first-child { position: sticky; left: 0; z-index: 2; min-width: 8rem; color: var(--color-ink-muted); background: var(--color-surface-raised); }
  thead th { position: sticky; top: 0; z-index: 1; background: var(--color-surface-raised); }
  thead th:first-child { z-index: 3; }
  thead span { display: block; max-width: 11rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  thead small { display: block; min-height: .8rem; margin-top: .12rem; color: var(--color-accent-strong); font-size: .52rem; text-transform: uppercase; }
  .reference { background: color-mix(in srgb, var(--color-positive-surface) 55%, var(--color-surface-raised)); }
  .viewing { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-accent-strong) 55%, transparent); }
  p { margin: 0; padding: .65rem .7rem; border-top: 1px solid var(--color-border-subtle); color: var(--color-ink-muted); font-size: .64rem; }

  .overlay-view { position: fixed; z-index: 30; inset: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); color: white; background: rgb(0 0 0 / 94%); }
  .overlay-view header { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(12rem, .7fr) auto; gap: .8rem; align-items: center; padding: .65rem .8rem; border-bottom: 1px solid rgb(255 255 255 / 18%); background: rgb(0 0 0 / 82%); }
  .overlay-view header > div, .overlay-view label { display: grid; gap: .15rem; min-width: 0; }
  .overlay-view header strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .7rem; }
  .overlay-view header span { color: rgb(255 255 255 / 70%); font-size: .56rem; }
  .overlay-view header button { min-height: 2.1rem; padding: .35rem .6rem; border: 1px solid rgb(255 255 255 / 35%); border-radius: var(--radius-sm); color: white; background: rgb(255 255 255 / 10%); cursor: pointer; }
  .overlay-stage { position: relative; display: grid; min-width: 0; min-height: 0; place-items: center; overflow: hidden; }
  .overlay-stage img { position: absolute; width: 100%; height: 100%; object-fit: contain; user-select: none; }
  .comparison-layer { pointer-events: none; }

  @media (max-width: 64rem) {
    .comparison-matrix { width: min(34rem, calc(100% - 1.5rem)); }
    .overlay-view header { grid-template-columns: 1fr 1fr; }
  }
</style>
