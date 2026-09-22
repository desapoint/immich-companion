<script lang="ts">
  import V2ViewerShell from '../../assets/components/ViewerShell.svelte';
  import V2LazyAssetMedia from '../../assets/components/LazyAssetMedia.svelte';
  import V2ImageComparison, { type ComparisonMode } from '../../duplicates/components/ImageComparison.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import { assetThumbnailUrl } from '../../../lib/utils/viewerMedia';
  import type { AssetRecord, MediaResource } from '../../../lib/types/libraryContracts';
  import type { LocalChangeDiagnostics } from '../../duplicates/utils/localChangeDiagnostics';
  import type { SimilarityDebugPair, SimilarityDebugValidationMode } from '../api/similarityDebug';

  let {
    open,
    assetIds = [],
    assets = [],
    pairs = [],
    pair = null,
    anchorAssetId = '',
    validationMode,
    similarityThreshold,
    onclose,
    onpairchange,
    onsetanchor,
  }: {
    open: boolean;
    assetIds?: string[];
    assets?: AssetRecord[];
    pairs?: SimilarityDebugPair[];
    pair?: SimilarityDebugPair | null;
    anchorAssetId?: string;
    validationMode: SimilarityDebugValidationMode;
    similarityThreshold: number;
    onclose: () => void;
    onpairchange: (pairKey: string) => void;
    onsetanchor: (assetId: string, compareWithAssetId: string) => void | Promise<void>;
  } = $props();

  let mode = $state<ComparisonMode>('Side by side');
  let split = $state(50);
  let opacity = $state(50);
  let diffHue = $state(190);
  let diffContrast = $state(180);
  let diffBinary = $state(true);
  let diffTolerance = $state(8);

  const assetById = $derived(new Map(assets.map((asset) => [asset.id, asset])));
  const pairByKey = $derived(new Map(pairs.map((candidate) => [pairKey(candidate.asset_id_left, candidate.asset_id_right), candidate])));
  const referenceId = $derived(pair?.asset_id_left ?? '');
  const selectedId = $derived(pair?.asset_id_right ?? '');
  const referenceAsset = $derived(referenceId ? assetById.get(referenceId) : undefined);
  const selectedAsset = $derived(selectedId ? assetById.get(selectedId) : undefined);
  const referenceResource = $derived(comparisonResource(referenceAsset));
  const selectedResource = $derived(comparisonResource(selectedAsset));
  const localDiagnostics = $derived(toLocalDiagnostics(pair));
  const comparisonTargets = $derived(assetIds.filter((assetId) => assetId !== referenceId));
  const selectedTargetIndex = $derived(Math.max(0, comparisonTargets.indexOf(selectedId)));

  function pairKey(left: string, right: string): string {
    return left < right ? `${left}\u0000${right}` : `${right}\u0000${left}`;
  }

  function comparisonResource(asset: AssetRecord | undefined): MediaResource {
    if (!asset) {
      return { url: '', fallbackUrls: [], mimeType: null, posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null };
    }
    return {
      url: assetThumbnailUrl(asset.id, 'preview'),
      fallbackUrls: [assetThumbnailUrl(asset.id, 'thumbnail')],
      mimeType: 'image/jpeg',
      posterUrl: null,
      delivery: 'preview',
      originalMimeType: asset.original_mime_type,
      expiresAt: null,
    };
  }

  function toLocalDiagnostics(candidate: SimilarityDebugPair | null): LocalChangeDiagnostics | null {
    const local = candidate?.local_diagnostics;
    if (!candidate || !local) return null;
    return {
      available: true,
      selectedAssetId: candidate.asset_id_right,
      referenceAssetId: candidate.asset_id_left,
      changedPercent: local.changed_percent,
      localizedChangedPercent: local.localized_changed_percent,
      coherentChangedPercent: local.coherent_changed_percent,
      largestChangedRegionPercent: local.largest_changed_region_percent,
      substantialRegionCount: local.substantial_region_count,
      alignedChangedPercent: local.aligned_changed_percent,
      rawSimilarityPercent: local.raw_similarity_percent,
      alignedSimilarityPercent: local.aligned_similarity_percent,
      alignmentApplied: local.alignment_applied,
      alignmentShiftPercent: local.alignment_shift_percent,
      alignmentOverlapPercent: local.alignment_overlap_percent,
      rows: local.rows,
      columns: local.columns,
      cells: local.cells,
      source: local.source,
    };
  }

  function assetName(assetId: string): string {
    return assetById.get(assetId)?.original_file_name ?? assetId;
  }

  function formatPercent(value: number | null | undefined, digits = 1): string {
    return value === null || value === undefined ? '—' : `${value.toFixed(digits)}%`;
  }

  function formatRatio(value: number | null | undefined): string {
    return value === null || value === undefined ? '—' : value.toFixed(4);
  }

  function pairStatus(candidate: SimilarityDebugPair | null): string {
    if (!candidate?.evidence_available) return 'No evidence';
    if (candidate.would_pass_pair_pipeline) return 'Pair-local pass';
    if (candidate.exclusion_reason === 'invalid_candidate_feature') return 'Invalid feature';
    if (candidate.exclusion_reason === 'perceptual_distance') return 'Rejected by pHash gate';
    if (candidate.exclusion_reason === 'aspect_ratio') return 'Rejected by aspect gate';
    if (candidate.exclusion_reason === 'similarity_threshold') return 'Below score threshold';
    return 'Excluded';
  }

  function modeLabel(value: SimilarityDebugValidationMode): string {
    if (value === 'reference') return 'Reference';
    if (value === 'linked') return 'Linked';
    return 'Strict';
  }

  function selectAgainstReference(assetId: string): void {
    if (!referenceId || assetId === referenceId) return;
    const key = pairKey(referenceId, assetId);
    if (pairByKey.has(key)) onpairchange(key);
  }

  function step(direction: 'previous' | 'next'): void {
    if (!comparisonTargets.length) return;
    const delta = direction === 'next' ? 1 : -1;
    const nextIndex = (selectedTargetIndex + delta + comparisonTargets.length) % comparisonTargets.length;
    selectAgainstReference(comparisonTargets[nextIndex] ?? '');
  }

  function setAnchor(assetId: string, compareWithAssetId: string): void {
    if (!assetId || !compareWithAssetId || assetId === compareWithAssetId) return;
    void onsetanchor(assetId, compareWithAssetId);
  }

  function editableTarget(target: EventTarget | null): boolean {
    return target instanceof Element && Boolean(target.closest('input,textarea,select,[contenteditable="true"]'));
  }

  function handleShortcut(event: KeyboardEvent): void {
    if (!open || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || editableTarget(event.target)) return;
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      step('previous');
      return;
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      step('next');
      return;
    }
    if ((event.key === 'r' || event.key === 'R') && selectedId && referenceId) {
      event.preventDefault();
      setAnchor(selectedId, referenceId);
      return;
    }
    const modes: Record<string, ComparisonMode> = {
      '1': 'Side by side',
      '2': 'Swipe',
      '3': 'Transparency',
      '4': 'Difference',
      '5': 'Local changes',
      '6': 'Flicker',
    };
    const nextMode = modes[event.key];
    if (nextMode) {
      event.preventDefault();
      mode = nextMode;
    }
  }
</script>

<svelte:window onkeydown={handleShortcut}/>

<V2ViewerShell {open} title="Similarity debug comparison" kind="compare" {onclose}>
  {#snippet header()}
    <div class="v2-compare-header-identity">
      <V2Button onclick={onclose}>✕</V2Button>
      <b class="v2-compare-group-title">Similarity debug comparison</b>
      <V2Badge text={modeLabel(validationMode)}/>
      <V2Badge text={`${formatPercent(similarityThreshold)} threshold`}/>
      {#if pair}
        <V2Badge tone={pair.would_pass_pair_pipeline ? 'ok' : 'warn'} text={pairStatus(pair)}/>
      {/if}
      {#if anchorAssetId}
        <V2Badge text={`Anchor: ${assetName(anchorAssetId)}`}/>
      {/if}
    </div>
    <div class="v2-compare-header-actions">
      <V2Button disabled={!comparisonTargets.length} onclick={() => step('previous')}>← Previous image</V2Button>
      <V2Button disabled={!comparisonTargets.length} onclick={() => step('next')}>Next image →</V2Button>
      <V2Button disabled={!selectedId || !referenceId || selectedId === anchorAssetId} onclick={() => setAnchor(selectedId, referenceId)}>Set selected as anchor</V2Button>
    </div>
  {/snippet}

  <div class="v2-compare-main">
    <section class="v2-compare-visual">
      {#if pair}
        <V2ImageComparison
          {selectedResource}
          {referenceResource}
          selectedLabel={assetName(selectedId)}
          referenceLabel={assetName(referenceId)}
          bind:mode
          bind:opacity
          bind:split
          bind:diffHue
          bind:diffContrast
          bind:diffBinary
          bind:diffTolerance
          {localDiagnostics}
        />

        <div class="similarity-debug-pair-roles">
          <div class:anchor={referenceId === anchorAssetId}>
            <span class="v2-small v2-muted">Reference side</span>
            <b title={assetName(referenceId)}>{assetName(referenceId)}</b>
            {#if referenceId === anchorAssetId}
              <V2Badge tone="ok" text="Anchor"/>
            {:else}
              <V2Button onclick={() => setAnchor(referenceId, selectedId)}>Set as anchor</V2Button>
            {/if}
          </div>
          <div class:anchor={selectedId === anchorAssetId}>
            <span class="v2-small v2-muted">Selected side</span>
            <b title={assetName(selectedId)}>{assetName(selectedId)}</b>
            {#if selectedId === anchorAssetId}
              <V2Badge tone="ok" text="Anchor"/>
            {:else}
              <V2Button onclick={() => setAnchor(selectedId, referenceId)}>Set as anchor</V2Button>
            {/if}
          </div>
        </div>

        <div class="v2-filmstrip">
          {#each assetIds as assetId (assetId)}
            {@const asset = assetById.get(assetId)}
            <div class="similarity-debug-filmstrip-item">
              <button
                class="v2-thumb"
                class:active={assetId === selectedId}
                class:reference={assetId === referenceId}
                title={assetName(assetId)}
                onclick={() => selectAgainstReference(assetId)}
              >
                {#if asset}
                  <span class="v2-thumb-media">
                    <V2LazyAssetMedia cacheKey={`similarity-debug-compare-thumbnail:${asset.id}`} resolve={() => libraryData.media.thumbnail(asset)} alt={asset.original_file_name}/>
                  </span>
                {/if}
                <small>{assetName(assetId)}</small>
                <small class="v2-muted">
                  {assetId === referenceId ? 'Reference side' : assetId === anchorAssetId ? 'Anchor' : 'Compare'}
                </small>
              </button>
              {#if assetId !== anchorAssetId && assetId !== referenceId}
                <button class="similarity-debug-anchor-action" onclick={() => setAnchor(assetId, referenceId)}>Set as anchor</button>
              {:else if assetId === anchorAssetId}
                <span class="similarity-debug-anchor-label">Anchor</span>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="similarity-debug-empty">Choose a pair from the matrix to inspect it.</div>
      {/if}
    </section>

    <aside class="v2-compare-data">
      {#if pair}
        <div class="v2-compare-header-zone">
          <V2Section title="Quick comparison">
            <div class="similarity-debug-summary">
              <div><span>Final similarity</span><b>{formatPercent(pair.similarity_percent)}</b></div>
              <div><span>Pair-local pipeline</span><b data-pass={pair.would_pass_pair_pipeline}>{pair.would_pass_pair_pipeline ? 'Pass' : 'Reject'}</b></div>
              <div><span>Reason</span><b>{pair.exclusion_reason ?? 'None'}</b></div>
              <div><span>Score threshold</span><b data-pass={pair.similarity_threshold_pass}>{formatPercent(pair.similarity_percent)} / {formatPercent(pair.similarity_threshold)}</b></div>
              <div><span>Configured anchor</span><b>{anchorAssetId ? assetName(anchorAssetId) : 'Automatic'}</b></div>
              <div><span>Neighbor allocation</span><b>Not simulated</b></div>
            </div>
          </V2Section>
        </div>

        <div class="similarity-debug-sidebar-scroll">
          <V2Section title="Pipeline evidence">
            <div class="similarity-debug-kv">
              <span>pHash distance</span><b data-pass={pair.perceptual_gate_pass}>{pair.perceptual_distance ?? '—'} / {pair.maximum_perceptual_distance}</b>
              <span>Aspect difference</span><b data-pass={pair.aspect_gate_pass}>{formatRatio(pair.aspect_ratio_difference)} / {pair.maximum_aspect_difference.toFixed(4)}</b>
              <span>Structure</span><b>{formatPercent(pair.structural_percent)}</b>
              <span>Perceptual score</span><b>{formatPercent(pair.perceptual_percent)}</b>
              <span>Color</span><b>{formatPercent(pair.color_percent)}</b>
              <span>Luminance MAE</span><b>{pair.normalized_luminance_mae ?? '—'}</b>
              <span>Luminance RMSE</span><b>{pair.normalized_luminance_rmse ?? '—'}</b>
              <span>Luminance SSIM</span><b>{pair.normalized_luminance_ssim ?? '—'}</b>
              <span>Dimensions equal</span><b>{pair.dimensions_equal === null ? '—' : pair.dimensions_equal ? 'Yes' : 'No'}</b>
              <span>Exact thumbnail</span><b>{pair.exact_thumbnail_match === null ? '—' : pair.exact_thumbnail_match ? 'Yes' : 'No'}</b>
              <span>Aligned detail changed</span><b>{formatPercent(pair.detail_changed_percent)}</b>
              <span>Detail source</span><b>{pair.detail_source ?? '—'}</b>
              <span>Evidence version</span><b>{pair.model_version ?? '—'} / f{pair.feature_version ?? '—'} / c{pair.comparison_version ?? '—'}</b>
            </div>
          </V2Section>

          <V2Section title="Localized detail diagnostics">
            {#if pair.local_diagnostics}
              {@const local = pair.local_diagnostics}
              <div class="similarity-debug-kv">
                <span>Raw detail similarity</span><b>{formatPercent(local.raw_similarity_percent)}</b>
                <span>Aligned detail similarity</span><b>{formatPercent(local.aligned_similarity_percent)}</b>
                <span>Raw changed area</span><b>{formatPercent(local.changed_percent)}</b>
                <span>Aligned changed area</span><b>{formatPercent(local.aligned_changed_percent)}</b>
                <span>Peak local change</span><b>{formatPercent(local.localized_changed_percent)}</b>
                <span>Coherent changed area</span><b>{formatPercent(local.coherent_changed_percent)}</b>
                <span>Largest changed region</span><b>{formatPercent(local.largest_changed_region_percent)}</b>
                <span>Substantial regions</span><b>{local.substantial_region_count}</b>
                <span>Alignment applied</span><b>{local.alignment_applied ? 'Yes' : 'No'}</b>
                <span>Alignment shift</span><b>{formatPercent(local.alignment_shift_percent)}</b>
                <span>Alignment overlap</span><b>{formatPercent(local.alignment_overlap_percent)}</b>
                <span>Evidence source</span><b>{local.source}</b>
              </div>
              <div class="similarity-debug-cell-grid" style={`--columns:${local.columns}`}>
                {#each local.cells.flat() as value, index}
                  <span title={`Cell ${index + 1}: ${formatPercent(value)}`} style={`--change:${Math.max(8, Math.round(value))}%`}>{Math.round(value)}</span>
                {/each}
              </div>
            {:else}
              <span class="v2-muted">Localized detail evidence is unavailable for this pair.</span>
            {/if}
          </V2Section>
        </div>
      {/if}
    </aside>
  </div>

  {#snippet footer()}
    <div class="similarity-debug-footer-copy">
      <b>Debug scope</b>
      <span>Only the selected debug images are evaluated. Full-library neighbor allocation is not simulated.</span>
    </div>
    <div class="similarity-debug-footer-actions">
      <span class="v2-small v2-muted">R sets the selected image as anchor · 1–6 switches comparison mode</span>
      <V2Button onclick={onclose}>Close comparison</V2Button>
    </div>
  {/snippet}
</V2ViewerShell>

<style>
  .v2-compare-header-identity,.v2-compare-header-actions{display:flex;align-items:center;gap:var(--v2-space-2);flex-wrap:wrap;min-width:0;max-width:100%}
  .v2-compare-header-identity{flex:1 1 360px}
  .v2-compare-header-actions{flex:0 1 auto;justify-content:flex-end}
  .v2-compare-group-title{display:block;min-width:0;max-width:min(34rem,42vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-thumb-media{position:relative;display:block;width:92px;height:92px;overflow:hidden;border-radius:5px}
  .v2-compare-data{display:grid;grid-template-rows:auto minmax(0,1fr);gap:12px;overflow:hidden}
  .v2-compare-header-zone{min-width:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable both-edges}
  .similarity-debug-sidebar-scroll{display:grid;gap:12px;min-height:0;overflow:auto;scrollbar-gutter:stable both-edges}
  .similarity-debug-pair-roles{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:8px 0}
  .similarity-debug-pair-roles>div{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:3px 8px;min-width:0;padding:8px 10px;border:1px solid var(--v2-line);border-radius:7px;background:var(--v2-surface)}
  .similarity-debug-pair-roles>div.anchor{outline:1px solid color-mix(in srgb,var(--v2-accent) 65%,transparent)}
  .similarity-debug-pair-roles b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .similarity-debug-pair-roles .v2-small{grid-column:1/-1}
  .similarity-debug-filmstrip-item{display:grid;gap:4px;justify-items:center;min-width:0}
  .similarity-debug-anchor-action{border:0;background:transparent;color:var(--v2-accent);font-size:.68rem;cursor:pointer;padding:2px 4px}
  .similarity-debug-anchor-label{color:#8fd694;font-size:.68rem;font-weight:700;padding:2px 4px}
  .similarity-debug-summary{display:grid;gap:7px}
  .similarity-debug-summary>div{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:baseline}
  .similarity-debug-summary span,.similarity-debug-kv span{color:var(--v2-muted)}
  .similarity-debug-summary b,.similarity-debug-kv b{text-align:right;overflow-wrap:anywhere}
  .similarity-debug-summary b[data-pass="true"],.similarity-debug-kv b[data-pass="true"]{color:#8fd694}
  .similarity-debug-summary b[data-pass="false"],.similarity-debug-kv b[data-pass="false"]{color:#ef9a9a}
  .similarity-debug-kv{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px 12px;align-items:baseline}
  .similarity-debug-cell-grid{display:grid;grid-template-columns:repeat(var(--columns),minmax(22px,1fr));gap:2px;margin-top:12px;max-height:260px;overflow:auto}
  .similarity-debug-cell-grid span{display:grid;place-items:center;aspect-ratio:1;background:color-mix(in srgb,var(--v2-accent) var(--change),transparent);font-size:9px;color:var(--v2-text)}
  .similarity-debug-footer-copy,.similarity-debug-footer-actions{display:flex;align-items:center;gap:10px;min-width:0}
  .similarity-debug-footer-copy{flex:1 1 auto}
  .similarity-debug-footer-copy span{color:var(--v2-muted);font-size:.75rem}
  .similarity-debug-footer-actions{justify-content:flex-end;flex-wrap:wrap}
  .similarity-debug-empty{display:grid;place-items:center;height:100%;color:var(--v2-muted)}
  @media(max-width:720px){
    .v2-compare-group-title{max-width:calc(100vw - 8rem)}
    .v2-compare-header-actions{justify-content:flex-start}
    .v2-compare-data{display:flex;overflow:visible}
    .similarity-debug-pair-roles{grid-template-columns:1fr}
    .similarity-debug-summary>div,.similarity-debug-kv{grid-template-columns:1fr}
    .similarity-debug-summary b,.similarity-debug-kv b{text-align:left}
    .similarity-debug-footer-copy,.similarity-debug-footer-actions{align-items:flex-start}
  }
</style>
