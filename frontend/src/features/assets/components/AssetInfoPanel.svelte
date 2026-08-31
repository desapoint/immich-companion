<script lang="ts">
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import { formatAssetDate } from '../state/assetViewModel';
  import type { AssetDetail, AssetSummary, DuplicateReviewContext } from '../types/assets';
  import AssetInfoRelationships from './AssetInfoRelationships.svelte';

  interface Props {
    asset: AssetSummary;
    detail: AssetDetail | null;
    loading: boolean;
    error: string | null;
    reserveComparisonTray?: boolean;
    syncing?: boolean;
    syncError?: string | null;
    onsync?: () => void;
    apiOnly?: boolean;
    duplicateContext?: DuplicateReviewContext | null;
    onduplicatekeeper?: (assetId: string) => void;
    onduplicateaction?: (action: DuplicateReviewContext['selected_action']) => void;
    onduplicatesimilarityreference?: (assetId: string) => void;
    onduplicatepreviousgroup?: () => void;
    onduplicatenextgroup?: () => void;
  }

  let {
    asset,
    detail,
    loading,
    error,
    reserveComparisonTray = false,
    syncing = false,
    syncError = null,
    onsync = () => undefined,
    apiOnly = false,
    duplicateContext = null,
    onduplicatekeeper,
    onduplicateaction,
    onduplicatesimilarityreference,
    onduplicatepreviousgroup,
    onduplicatenextgroup,
  }: Props = $props();

  const duplicateActionOptions = $derived<SelectOption[]>([
    { value: 'automatic', label: 'Automatic recommendation' },
    { value: 'none', label: 'Skip / review later' },
    {
      value: 'resolve',
      label: 'Resolve — keep primary',
      disabled: !duplicateContext?.eligible,
    },
    { value: 'keep_all', label: 'Keep all — reviewed copies' },
    { value: 'delete_all', label: 'Delete all — keep no copy' },
    {
      value: 'stack_all',
      label: 'Stack all — keep every copy',
      disabled: duplicateContext?.members.some((member) => member.is_offline || member.is_stacked),
    },
  ]);

  const currentDuplicateMember = $derived(
    duplicateContext?.members.find((member) => member.id === asset.id) ?? null,
  );
  const automaticRuleRespected = $derived(
    duplicateContext !== null
      && duplicateContext.recommended_keeper_asset_id !== null
      && duplicateContext.selected_keeper_asset_id === duplicateContext.recommended_keeper_asset_id,
  );
  const currentSimilarity = $derived(currentDuplicateMember?.similarity ?? null);
  const currentPreservation = $derived(currentDuplicateMember?.preservation ?? null);

  function formatBytes(value: number | null): string {
    if (value === null) return 'Unavailable';
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }

  function keeperPolicyLabel(value: DuplicateReviewContext['keeper_policy']): string {
    if (value === 'most_recent') return 'Most recently uploaded';
    if (value === 'prefer_upload') return 'Prefer Immich uploads';
    if (value === 'prefer_external') return 'Prefer external files';
    return 'Keep first Immich result';
  }

  function displayValue(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    return JSON.stringify(value);
  }
</script>

<aside
  class:reserve-comparison-tray={reserveComparisonTray}
  class="info-panel"
  aria-label="Image details"
>
  <header>
    <div class="header-label">
      <span>More info</span>
      {#if !apiOnly}<button type="button" class="sync-button" onclick={onsync} disabled={syncing}>
        <Icon name="sync" size="0.85rem" />
        <span>{syncing ? 'Syncing…' : 'Sync'}</span>
      </button>{/if}
    </div>
    <strong title={detail?.original_file_name ?? asset.original_file_name}>{detail?.original_file_name ?? asset.original_file_name}</strong>
    {#if syncError}<p class="error sync-error" role="alert">{syncError}</p>{/if}
  </header>

  {#if !apiOnly}<AssetInfoRelationships {asset} />{/if}

  {#if duplicateContext}
    <section class="duplicate-review" aria-label="Duplicate group validation">
      <div class="section-heading"><h3>Duplicate review</h3><span class={`duplicate-status ${duplicateContext.status}`}>{duplicateContext.status}</span></div>
      <p>{duplicateContext.reason ?? 'No group explanation was provided.'}</p>
      {#if onduplicateaction && onduplicatekeeper}
        <div class="duplicate-controls">
          <SelectField
            id={`viewer-duplicate-action-${duplicateContext.duplicate_id}`}
            label="Group action"
            value={duplicateContext.selected_action}
            options={duplicateActionOptions}
            compact
            onchange={(value) => onduplicateaction?.(value as DuplicateReviewContext['selected_action'])}
          />
          <button
            type="button"
            class:active-primary={duplicateContext.selected_keeper_asset_id === asset.id}
            onclick={() => onduplicatekeeper?.(asset.id)}
          >
            {duplicateContext.selected_keeper_asset_id === asset.id ? 'Selected primary' : 'Use viewed as primary'}
          </button>
        </div>
      {/if}
      {#if onduplicatepreviousgroup || onduplicatenextgroup}
        <div class="duplicate-group-navigation" aria-label="Duplicate group navigation">
          <button type="button" disabled={!onduplicatepreviousgroup} onclick={() => onduplicatepreviousgroup?.()}>← Previous group</button>
          <button type="button" disabled={!onduplicatenextgroup} onclick={() => onduplicatenextgroup?.()}>Next group →</button>
        </div>
      {/if}
      <dl>
        <div><dt>Group ID</dt><dd>{duplicateContext.duplicate_id}</dd></div>
        <div><dt>Matching type</dt><dd>{duplicateContext.status === 'exact' ? 'Byte-exact content' : duplicateContext.status}</dd></div>
        <div><dt>Batch eligible</dt><dd>{duplicateContext.eligible ? 'Yes' : 'No'}</dd></div>
        <div><dt>Keeper rule</dt><dd>{keeperPolicyLabel(duplicateContext.keeper_policy)}</dd></div>
        <div><dt>Auto rule followed</dt><dd class:positive={automaticRuleRespected} class:warning={!automaticRuleRespected}>{duplicateContext.recommended_keeper_asset_id === null ? 'No unique recommendation' : automaticRuleRespected ? 'Yes' : 'No — manually overridden'}</dd></div>
        <div><dt>This copy</dt><dd>{duplicateContext.selected_action === 'delete_all' ? 'Will be trashed' : duplicateContext.selected_action === 'keep_all' ? 'Will be retained' : duplicateContext.selected_keeper_asset_id === null ? 'Undecided' : duplicateContext.selected_keeper_asset_id === asset.id ? 'Selected primary' : duplicateContext.selected_action === 'resolve' ? 'Will be removed' : duplicateContext.selected_action === 'stack_all' ? 'Retained in stack' : 'No change planned'}</dd></div>
        <div><dt>Rule recommendation</dt><dd>{duplicateContext.recommended_keeper_asset_id === null ? 'None — manual choice required' : duplicateContext.recommended_keeper_asset_id === asset.id ? 'Keep this copy' : 'Keep another copy'}</dd></div>
        <div><dt>Decision reasons</dt><dd>{duplicateContext.recommendation_reason_codes.join(', ') || 'No automatic recommendation'}</dd></div>
      </dl>

      <h4>Current copy validation</h4>
      {#if onduplicatesimilarityreference}
        <button
          class="similarity-reference-button"
          class:active-reference={currentSimilarity?.state === 'reference'}
          type="button"
          disabled={duplicateContext.similarity_loading || currentSimilarity?.state === 'reference'}
          onclick={() => onduplicatesimilarityreference?.(asset.id)}
        >
          {duplicateContext.similarity_loading
            ? 'Changing similarity reference…'
            : currentSimilarity?.state === 'reference'
              ? 'Viewed copy is similarity reference'
              : 'Use viewed as similarity reference'}
        </button>
        {#if duplicateContext.similarity_error}
          <p class="error" role="alert">{duplicateContext.similarity_error}</p>
        {/if}
      {/if}
      <dl>
        <div><dt>Content SHA-1</dt><dd>{currentDuplicateMember?.verification ?? 'unverified'}</dd></div>
        <div><dt>Source</dt><dd>{currentDuplicateMember?.source_kind === 'external' ? 'External library' : 'Immich upload'}</dd></div>
        <div><dt>Library ID</dt><dd>{currentDuplicateMember?.library_id ?? 'Upload storage'}</dd></div>
        <div><dt>File size</dt><dd>{formatBytes(currentDuplicateMember?.file_size_bytes ?? null)}</dd></div>
        <div><dt>Availability</dt><dd>{currentDuplicateMember?.is_offline ? 'Offline / unverified' : 'Available'}</dd></div>
        <div><dt>Existing stack</dt><dd>{currentDuplicateMember?.is_stacked ? 'Already stacked' : 'None'}</dd></div>
        <div><dt>Integrity cache</dt><dd>{duplicateContext.current_integrity?.freshness ?? 'missing'}</dd></div>
        <div><dt>Structure</dt><dd>{duplicateContext.current_integrity?.report?.classification ?? 'Not analyzed'}</dd></div>
        <div><dt>Visual similarity</dt><dd>{currentSimilarity?.state === 'reference' ? 'Reference (100%)' : currentSimilarity?.state === 'current' ? `${currentSimilarity.similarity_percent?.toFixed(2)}%` : currentSimilarity?.state ?? 'Not analyzed'}</dd></div>
        {#if currentSimilarity?.state === 'current'}
          <div><dt>Structure</dt><dd>{currentSimilarity.structural_percent?.toFixed(2)}%</dd></div>
          <div><dt>Perceptual hash</dt><dd>{currentSimilarity.perceptual_percent?.toFixed(2)}%</dd></div>
          <div><dt>Color</dt><dd>{currentSimilarity.color_percent?.toFixed(2)}%</dd></div>
          <div><dt>Normalized thumbnail</dt><dd>{currentSimilarity.exact_thumbnail_match ? 'Exact' : 'Different'}</dd></div>
          <div><dt>Normalized decoded pixels</dt><dd>{currentSimilarity.exact_pixel_match ? 'Exact' : 'Different'}</dd></div>
          <div><dt>Similarity model</dt><dd>{currentSimilarity.model_version ?? 'Unknown'} · comparison v{currentSimilarity.comparison_version ?? '?'}</dd></div>
        {/if}
        {#if currentPreservation}
          <div><dt>Normalized pixels</dt><dd>v{currentPreservation.pixel_normalization_version} · {currentPreservation.pixel_sha256}</dd></div>
          <div><dt>Decoded quality</dt><dd>{currentPreservation.decoded_width}×{currentPreservation.decoded_height} · {currentPreservation.bit_depth}-bit · {currentPreservation.channel_count} channels</dd></div>
          <div><dt>Color / alpha</dt><dd>{currentPreservation.color_space} · {currentPreservation.has_alpha ? 'alpha retained' : 'opaque'}</dd></div>
          <div><dt>Profile / orientation</dt><dd>{currentPreservation.icc_profile_present ? 'ICC profile' : 'No ICC profile'} · {currentPreservation.orientation === null ? 'no EXIF orientation' : `orientation ${currentPreservation.orientation}`}</dd></div>
          <div><dt>Metadata preservation</dt><dd>Richness {currentPreservation.metadata_richness}/6 · {currentPreservation.has_capture_time ? 'capture time' : 'no capture time'} · {currentPreservation.has_camera_info ? 'camera' : 'no camera'} · {currentPreservation.has_gps ? 'GPS' : 'no GPS'}</dd></div>
        {/if}
        <div><dt>Metadata comparison</dt><dd>Planned validation</dd></div>
        {#if currentDuplicateMember?.content_checksum}<div><dt>Content hash</dt><dd>{currentDuplicateMember.content_checksum}</dd></div>{/if}
      </dl>

      <details>
        <summary>All {duplicateContext.members.length} group members</summary>
        <ul class="duplicate-members">
          {#each duplicateContext.members as member (member.id)}
            <li class:current={member.id === asset.id}>
              <strong>{member.filename}</strong>
              <span>{member.source_kind === 'upload' ? 'Upload' : `External · ${member.library_id ?? 'unknown library'}`} · {member.verification}{member.id === duplicateContext.selected_keeper_asset_id ? ' · keeper' : ''}</span>
            </li>
          {/each}
        </ul>
      </details>
    </section>
  {/if}

  <h3>Immich metadata</h3>

  {#if loading}
    <p role="status">Loading image details…</p>
  {:else if error}
    <p class="error" role="alert">{error}</p>
  {:else if detail}
    <dl>
      <div><dt>Immich ID</dt><dd title={detail.id}>{detail.id}</dd></div>
      <div><dt>Filename</dt><dd>{detail.original_file_name}</dd></div>
      {#if detail.original_path}<div><dt>Path</dt><dd title={detail.original_path}>{detail.original_path}</dd></div>{/if}
      {#if detail.original_mime_type}<div><dt>MIME type</dt><dd>{detail.original_mime_type}</dd></div>{/if}
      <div><dt>Taken</dt><dd>{formatAssetDate(detail.taken_at)}</dd></div>
      <div><dt>Modified</dt><dd>{formatAssetDate(detail.file_modified_at)}</dd></div>
      {#if detail.owner_id}<div><dt>Owner ID</dt><dd>{detail.owner_id}</dd></div>{/if}
      {#if detail.library_id}<div><dt>Library ID</dt><dd>{detail.library_id}</dd></div>{/if}
      {#if detail.visibility}<div><dt>Visibility</dt><dd>{detail.visibility}</dd></div>{/if}
    </dl>

    {#if detail.exif_info && Object.keys(detail.exif_info).length}
      <details open>
        <summary>EXIF information</summary>
        <dl>
          {#each Object.entries(detail.exif_info) as [key, value] (key)}
            {#if value !== null && value !== ''}
              <div><dt>{key}</dt><dd>{displayValue(value)}</dd></div>
            {/if}
          {/each}
        </dl>
      </details>
    {/if}

    {#if detail.immich_url}
      <a href={detail.immich_url} target="_blank" rel="noopener noreferrer">Open this asset in Immich ↗</a>
    {/if}
  {:else}
    <p>No additional metadata is available.</p>
  {/if}
</aside>

<style>
  .info-panel {
    position: absolute;
    z-index: 4;
    top: 0.75rem;
    right: 1.5rem;
    width: min(26rem, calc(100% - 1.5rem));
    max-height: calc(100% - 1.5rem);
    padding: 0.9rem;
    overflow: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: color-mix(in srgb, var(--color-surface-raised) 96%, transparent);
    box-shadow: 0 1rem 3rem rgb(0 0 0 / 28%);
    backdrop-filter: blur(0.6rem);
  }

  .info-panel.reserve-comparison-tray {
    max-height: calc(100% - 8rem);
  }

  header {
    display: grid;
    gap: 0.16rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .header-label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .sync-button {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    padding: 0.24rem 0.42rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.65rem;
    font-weight: 760;
  }

  .sync-button:hover:not(:disabled),
  .sync-button:focus-visible {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  .sync-button:disabled {
    cursor: default;
    opacity: 0.55;
  }

  .sync-error {
    margin: 0.15rem 0 0;
  }

  header span {
    color: var(--color-accent-strong);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  header strong {
    overflow: hidden;
    font-size: 0.9rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  h3 {
    margin: 0.8rem 0 0;
    color: var(--color-accent-strong);
    font-size: 0.72rem;
  }

  h4 { margin: 0.8rem 0 0; font-size: 0.68rem; }
  .duplicate-review { margin-top: .8rem; padding: .65rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); background: var(--color-surface-soft); }
  .duplicate-review h3 { margin: 0; }
  .duplicate-review > p { margin: .45rem 0 0; color: var(--color-ink-muted); line-height: 1.45; }
  .duplicate-controls { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .5rem; align-items: end; margin-top: .65rem; }
  .duplicate-controls button { min-height: 2.35rem; padding: .45rem .6rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); cursor: pointer; font: inherit; font-size: .65rem; font-weight: 780; }
  .duplicate-controls button:hover, .duplicate-controls button:focus-visible, .duplicate-controls button.active-primary { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .duplicate-group-navigation { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-top: .5rem; }
  .duplicate-group-navigation button { min-width: 0; min-height: 2rem; padding: .35rem .5rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); cursor: pointer; font: inherit; font-size: .62rem; font-weight: 760; }
  .duplicate-group-navigation button:hover:not(:disabled), .duplicate-group-navigation button:focus-visible { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .duplicate-group-navigation button:disabled { opacity: .45; cursor: default; }
  .similarity-reference-button { width: 100%; min-height: 2.15rem; margin-top: .5rem; padding: .4rem .55rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); cursor: pointer; font: inherit; font-size: .64rem; font-weight: 780; }
  .similarity-reference-button:hover:not(:disabled), .similarity-reference-button:focus-visible, .similarity-reference-button.active-reference { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .similarity-reference-button:disabled { cursor: default; opacity: .65; }
  .section-heading { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
  .duplicate-status { padding: .16rem .38rem; border-radius: 999px; background: var(--color-canvas); font-size: .58rem; font-weight: 820; text-transform: uppercase; }
  .duplicate-status.exact, .positive { color: var(--color-positive-ink); }
  .duplicate-status.unverified, .warning { color: var(--color-warning-ink); }
  .duplicate-status.mismatch, .duplicate-status.ineligible { color: var(--color-negative-ink); }
  .duplicate-members { display: grid; gap: .4rem; margin: .55rem 0 0; padding: 0; list-style: none; }
  .duplicate-members li { display: grid; gap: .1rem; padding: .4rem; border-left: 2px solid var(--color-border-strong); background: var(--color-canvas); }
  .duplicate-members li.current { border-left-color: var(--color-accent-strong); }
  .duplicate-members strong { overflow: hidden; font-size: .66rem; text-overflow: ellipsis; white-space: nowrap; }
  .duplicate-members span { color: var(--color-ink-muted); font-size: .6rem; overflow-wrap: anywhere; }

  dl {
    display: grid;
    gap: 0.5rem;
    margin: 0.75rem 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(5rem, 0.38fr) minmax(0, 1fr);
    gap: 0.65rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  dt,
  dd,
  p,
  a,
  summary {
    font-size: 0.7rem;
  }

  dt {
    color: var(--color-ink-muted);
  }

  dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
    font-family: var(--font-mono);
  }

  details {
    margin-top: 0.8rem;
  }

  summary {
    color: var(--color-accent-strong);
    cursor: pointer;
    font-weight: 760;
  }

  a {
    display: inline-block;
    margin-top: 0.5rem;
    color: var(--color-accent-strong);
    font-weight: 760;
    text-underline-offset: 0.2rem;
  }

  .error {
    color: var(--color-negative-ink);
  }
</style>
