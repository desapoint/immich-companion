<script lang="ts">
  import { onMount } from 'svelte';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2LazyAssetMedia from '../../assets/components/LazyAssetMedia.svelte';
  import V2ImageComparison, { type ComparisonMode } from '../../duplicates/components/ImageComparison.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import { assetThumbnailUrl } from '../../../lib/utils/viewerMedia';
  import type { AssetRecord, MediaResource } from '../../../lib/types/libraryContracts';
  import type { LocalChangeDiagnostics } from '../../duplicates/utils/localChangeDiagnostics';
  import {
    clearSimilarityDebugAssets,
    readSimilarityDebugAssets,
    removeSimilarityDebugAsset,
    SIMILARITY_DEBUG_CHANGED_EVENT,
  } from '../state/similarityDebugBasket';
  import { duplicateDiscoverySettingsRepository } from '../../duplicates/api/duplicateDiscoverySettingsRepository';
  import {
    runSimilarityDebug,
    type SimilarityDebugPair,
    type SimilarityDebugResponse,
    type SimilarityDebugValidationMode,
  } from '../api/similarityDebug';

  let assetIds = $state<string[]>([]);
  let selected = $state<Set<string>>(new Set());
  let assets = $state<AssetRecord[]>([]);
  let response = $state<SimilarityDebugResponse | null>(null);
  let activePairKey = $state('');
  let loadingAssets = $state(false);
  let running = $state(false);
  let error = $state('');
  let comparisonMode = $state<ComparisonMode>('Side by side');
  let comparisonSplit = $state(50);
  let comparisonOpacity = $state(50);
  let diffHue = $state(190);
  let diffContrast = $state(180);
  let diffBinary = $state(true);
  let diffTolerance = $state(8);

  let similarityThreshold = $state(95);
  let validationMode = $state<SimilarityDebugValidationMode>('strict');
  let maxLinkDepth = $state(2);
  let maximumPerceptualDistance = $state(12);
  let maximumAspectDifference = $state(0.05);
  let maximumNeighborsPerAsset = $state(8);
  let anchorAssetId = $state<string>('');

  const checkedIds = $derived(assetIds.filter((id) => selected.has(id)));
  const assetById = $derived(new Map(assets.map((asset) => [asset.id, asset])));
  const resultAssetById = $derived(new Map((response?.assets ?? []).map((asset) => [asset.asset_id, asset])));
  const pairByKey = $derived(new Map((response?.pairs ?? []).map((pair) => [pairKey(pair.asset_id_left, pair.asset_id_right), pair])));
  const activePair = $derived(pairByKey.get(activePairKey) ?? null);
  const activeLeftAsset = $derived(activePair ? assetById.get(activePair.asset_id_left) : undefined);
  const activeRightAsset = $derived(activePair ? assetById.get(activePair.asset_id_right) : undefined);
  const activeLeftResource = $derived(comparisonResource(activeLeftAsset));
  const activeRightResource = $derived(comparisonResource(activeRightAsset));
  const activeLocalDiagnostics = $derived(toLocalDiagnostics(activePair));

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

  function toLocalDiagnostics(pair: SimilarityDebugPair | null): LocalChangeDiagnostics | null {
    const local = pair?.local_diagnostics;
    if (!pair || !local) return null;
    return {
      available: true,
      selectedAssetId: pair.asset_id_left,
      referenceAssetId: pair.asset_id_right,
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

  function formatPercent(value: number | null | undefined, digits = 1): string {
    return value === null || value === undefined ? '—' : `${value.toFixed(digits)}%`;
  }

  function formatRatio(value: number | null | undefined): string {
    return value === null || value === undefined ? '—' : value.toFixed(4);
  }

  function pairStatus(pair: SimilarityDebugPair | undefined): string {
    if (!pair?.evidence_available) return 'No evidence';
    if (pair.would_pass_pair_pipeline) return 'Pass';
    if (pair.exclusion_reason === 'perceptual_distance') return 'pHash gate';
    if (pair.exclusion_reason === 'aspect_ratio') return 'Aspect gate';
    if (pair.exclusion_reason === 'similarity_threshold') return 'Score gate';
    return 'Excluded';
  }

  function assetName(assetId: string): string {
    return assetById.get(assetId)?.original_file_name ?? assetId;
  }

  async function loadDiscoveryDefaults(): Promise<void> {
    try {
      const settings = await duplicateDiscoverySettingsRepository.load();
      similarityThreshold = settings.similarityThreshold;
      validationMode = settings.validationMode;
      maxLinkDepth = settings.maxLinkDepth;
      maximumPerceptualDistance = settings.maximumPerceptualDistance;
      maximumNeighborsPerAsset = settings.maxCandidates;
    } catch {
      // Keep schema defaults when persisted discovery settings are unavailable.
    }
  }

  async function refreshBasket(): Promise<void> {
    const nextIds = readSimilarityDebugAssets();
    assetIds = nextIds;
    selected = new Set([...selected].filter((id) => nextIds.includes(id)));
    if (!selected.size) selected = new Set(nextIds);
    if (anchorAssetId && !nextIds.includes(anchorAssetId)) anchorAssetId = '';
    loadingAssets = true;
    try {
      assets = nextIds.length ? await libraryData.assets.getMany(nextIds) : [];
    } finally {
      loadingAssets = false;
    }
  }

  function toggle(assetId: string, checked: boolean): void {
    const next = new Set(selected);
    if (checked) next.add(assetId);
    else next.delete(assetId);
    selected = next;
    response = null;
    activePairKey = '';
  }

  async function analyze(): Promise<void> {
    if (checkedIds.length < 2) {
      error = 'Choose at least two debug images.';
      return;
    }
    running = true;
    error = '';
    activePairKey = '';
    try {
      response = await runSimilarityDebug({
        asset_ids: checkedIds,
        similarity_threshold: similarityThreshold,
        validation_mode: validationMode,
        max_link_depth: maxLinkDepth,
        anchor_asset_id: anchorAssetId && checkedIds.includes(anchorAssetId) ? anchorAssetId : null,
        maximum_perceptual_distance: maximumPerceptualDistance,
        maximum_aspect_difference: maximumAspectDifference,
      });
      const first = response.pairs[0];
      if (first) activePairKey = pairKey(first.asset_id_left, first.asset_id_right);
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Similarity diagnostics failed.';
      response = null;
    } finally {
      running = false;
    }
  }

  function remove(assetId: string): void {
    removeSimilarityDebugAsset(assetId);
    void refreshBasket();
  }

  function clear(): void {
    clearSimilarityDebugAssets();
    assetIds = [];
    assets = [];
    selected = new Set();
    response = null;
    activePairKey = '';
  }

  onMount(() => {
    void loadDiscoveryDefaults();
    void refreshBasket();
    const listener = () => void refreshBasket();
    window.addEventListener(SIMILARITY_DEBUG_CHANGED_EVENT, listener);
    return () => window.removeEventListener(SIMILARITY_DEBUG_CHANGED_EVENT, listener);
  });
</script>

<V2PageLayout
  title="Similarity debug"
  description="Compare explicitly selected images with the production similarity scorer and see which normal pipeline gates would pass or reject each pair."
>
  {#snippet headerActions()}
    <V2Inline gap="sm" wrap>
      <V2Badge text={`${assetIds.length} debug image${assetIds.length === 1 ? '' : 's'}`}/>
      <V2Button disabled={!assetIds.length} onclick={clear}>Clear debug list</V2Button>
    </V2Inline>
  {/snippet}

  <div class="similarity-debug-page">
    <V2Section title="Debug images">
      {#if loadingAssets}
        <V2Card><span class="v2-muted">Loading debug images…</span></V2Card>
      {:else if !assetIds.length}
        <V2Card><span class="v2-muted">Add images from Assets Viewer or Duplicate comparison, then return here to inspect them.</span></V2Card>
      {:else}
        <div class="similarity-debug-assets">
          {#each assetIds as assetId (assetId)}
            {@const asset = assetById.get(assetId)}
            {@const evidence = resultAssetById.get(assetId)}
            <V2Card class="similarity-debug-asset-card">
              <label class="similarity-debug-asset-select">
                <input type="checkbox" checked={selected.has(assetId)} onchange={(event) => toggle(assetId, event.currentTarget.checked)}>
                <span class="similarity-debug-thumb">
                  {#if asset}<V2LazyAssetMedia cacheKey={`similarity-debug:${asset.id}`} resolve={() => libraryData.media.thumbnail(asset)} alt={asset.original_file_name}/>{/if}
                </span>
                <span class="similarity-debug-asset-copy">
                  <b title={asset?.original_file_name ?? assetId}>{asset?.original_file_name ?? assetId}</b>
                  <small>{asset?.width ?? '—'} × {asset?.height ?? '—'}</small>
                  {#if evidence}
                    <small data-state={evidence.evidence_state}>{evidence.evidence_state === 'current' ? `Current · ${evidence.fingerprint_origin ?? 'unknown source'}` : evidence.reason ?? evidence.evidence_state}</small>
                  {/if}
                </span>
              </label>
              <V2Button onclick={() => remove(assetId)}>Remove</V2Button>
            </V2Card>
          {/each}
        </div>
      {/if}
    </V2Section>

    <V2Section title="Pipeline settings">
      <V2Card>
        <div class="similarity-debug-settings">
          <label>Similarity threshold <input type="number" min="50" max="100" step="0.1" bind:value={similarityThreshold}></label>
          <label>Validation mode <select bind:value={validationMode}><option value="reference">Reference</option><option value="linked">Linked</option><option value="strict">Strict</option></select></label>
          <label>Anchor <select bind:value={anchorAssetId}><option value="">Automatic</option>{#each checkedIds as id}<option value={id}>{assetName(id)}</option>{/each}</select></label>
          <label>Max link depth <input type="number" min="0" max="64" step="1" bind:value={maxLinkDepth}></label>
          <label>Max pHash distance <input type="number" min="0" max="64" step="1" bind:value={maximumPerceptualDistance}></label>
          <label>Max aspect difference <input type="number" min="0" max="1" step="0.01" bind:value={maximumAspectDifference}></label>
          <label>Library neighbor cap <input type="number" value={maximumNeighborsPerAsset} disabled></label>
        </div>
        <V2Inline gap="sm" wrap>
          <V2Button variant="primary" disabled={running || checkedIds.length < 2} onclick={() => void analyze()}>{running ? 'Analyzing…' : `Analyze ${checkedIds.length} selected`}</V2Button>
          <span class="v2-small v2-muted">Every checked pair is scored even when the normal candidate gates would reject it. The saved library neighbor cap is shown for context but is not simulated.</span>
        </V2Inline>
        {#if error}<p class="similarity-debug-error" role="alert">{error}</p>{/if}
      </V2Card>
    </V2Section>

    {#if response}
      <V2Section title="Pair matrix">
        <V2Card>
          <p class="v2-small v2-muted">{response.note}</p>
          <div class="similarity-debug-matrix-wrap">
            <table class="similarity-debug-matrix">
              <thead><tr><th>Image</th>{#each checkedIds as id}<th title={assetName(id)}>{assetName(id)}</th>{/each}</tr></thead>
              <tbody>
                {#each checkedIds as rowId}
                  <tr>
                    <th title={assetName(rowId)}>{assetName(rowId)}</th>
                    {#each checkedIds as columnId}
                      {#if rowId === columnId}
                        <td class="same">100%</td>
                      {:else}
                        {@const pair = pairByKey.get(pairKey(rowId, columnId))}
                        <td data-pass={pair?.would_pass_pair_pipeline ? 'true' : 'false'}>
                          <button type="button" class:active={activePairKey === pairKey(rowId, columnId)} onclick={() => activePairKey = pairKey(rowId, columnId)}>
                            <b>{formatPercent(pair?.similarity_percent)}</b>
                            <small>{pairStatus(pair)}</small>
                          </button>
                        </td>
                      {/if}
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </V2Card>
      </V2Section>

      {#if activePair}
        <V2Section title="Selected pair diagnostics">
          <div class="similarity-debug-detail-grid">
            <div class="similarity-debug-visual">
              <V2Card title="Visual comparison">
                <div class="similarity-debug-visual-stage">
                  <V2ImageComparison
                    selectedResource={activeLeftResource}
                    referenceResource={activeRightResource}
                    selectedLabel={assetName(activePair.asset_id_left)}
                    referenceLabel={assetName(activePair.asset_id_right)}
                    bind:mode={comparisonMode}
                    bind:split={comparisonSplit}
                    bind:opacity={comparisonOpacity}
                    bind:diffHue
                    bind:diffContrast
                    bind:diffBinary
                    bind:diffTolerance
                    localDiagnostics={activeLocalDiagnostics}
                  />
                </div>
              </V2Card>
            </div>
            <V2Card title={`${assetName(activePair.asset_id_left)} ↔ ${assetName(activePair.asset_id_right)}`}>
              <div class="similarity-debug-kv">
                <span>Final similarity</span><b>{formatPercent(activePair.similarity_percent)}</b>
                <span>Would pass pair-local pipeline</span><b data-pass={activePair.would_pass_pair_pipeline}>{activePair.would_pass_pair_pipeline ? 'Yes' : 'No'}</b>
                <span>Exclusion reason</span><b>{activePair.exclusion_reason ?? 'None'}</b>
                <span>pHash distance</span><b data-pass={activePair.perceptual_gate_pass}>{activePair.perceptual_distance ?? '—'} / {activePair.maximum_perceptual_distance}</b>
                <span>Aspect difference</span><b data-pass={activePair.aspect_gate_pass}>{formatRatio(activePair.aspect_ratio_difference)} / {activePair.maximum_aspect_difference.toFixed(4)}</b>
                <span>Score threshold</span><b data-pass={activePair.similarity_threshold_pass}>{formatPercent(activePair.similarity_percent)} / {formatPercent(activePair.similarity_threshold)}</b>
                <span>Neighbor allocation</span><b>Not simulated</b>
                <span>Structure</span><b>{formatPercent(activePair.structural_percent)}</b>
                <span>Perceptual score</span><b>{formatPercent(activePair.perceptual_percent)}</b>
                <span>Color</span><b>{formatPercent(activePair.color_percent)}</b>
                <span>Luminance MAE</span><b>{activePair.normalized_luminance_mae ?? '—'}</b>
                <span>Luminance RMSE</span><b>{activePair.normalized_luminance_rmse ?? '—'}</b>
                <span>Luminance SSIM</span><b>{activePair.normalized_luminance_ssim ?? '—'}</b>
                <span>Dimensions equal</span><b>{activePair.dimensions_equal === null ? '—' : activePair.dimensions_equal ? 'Yes' : 'No'}</b>
                <span>Exact thumbnail</span><b>{activePair.exact_thumbnail_match === null ? '—' : activePair.exact_thumbnail_match ? 'Yes' : 'No'}</b>
                <span>Aligned detail changed</span><b>{formatPercent(activePair.detail_changed_percent)}</b>
                <span>Detail source</span><b>{activePair.detail_source ?? '—'}</b>
                <span>Model</span><b>{activePair.model_version ?? '—'} / f{activePair.feature_version ?? '—'} / c{activePair.comparison_version ?? '—'}</b>
              </div>
            </V2Card>

            <V2Card title="Localized detail diagnostics">
              {#if activePair.local_diagnostics}
                {@const local = activePair.local_diagnostics}
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
            </V2Card>
          </div>
        </V2Section>
      {/if}

      <V2Section title="Selected-set group simulation">
        <V2Card>
          <p class="v2-small v2-muted">This groups only the checked images after pair-local candidate gates and the score threshold. Library-wide maximum-neighbor allocation is intentionally not simulated.</p>
          {#each response.groups as group, index}
            <div class="similarity-debug-group">
              <b>Group {index + 1} · {group.validation_mode} · minimum {formatPercent(group.minimum_similarity_percent)}</b>
              <span>Anchor: {assetName(group.anchor_asset_id)}</span>
              <div class="similarity-debug-admissions">
                {#each group.admission_evidence as admission}
                  <span><b>{assetName(admission.asset_id)}</b>{#if admission.admitted_by_asset_id} ← {assetName(admission.admitted_by_asset_id)} at {formatPercent(admission.admission_similarity_percent)} · depth {admission.link_depth}{/if}</span>
                {/each}
              </div>
            </div>
          {:else}
            <span class="v2-muted">No group would form from the selected pair-local passing edges.</span>
          {/each}
        </V2Card>
      </V2Section>
    {/if}
  </div>
</V2PageLayout>

<style>
  .similarity-debug-page{display:grid;gap:var(--v2-space-4);min-width:0}
  .similarity-debug-assets{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:var(--v2-space-3)}
  .similarity-debug-asset-card{display:flex;align-items:center;justify-content:space-between;gap:10px;min-width:0}
  .similarity-debug-asset-select{display:flex;align-items:center;gap:10px;min-width:0;cursor:pointer}
  .similarity-debug-thumb{position:relative;display:block;width:64px;height:64px;flex:0 0 64px;overflow:hidden;border-radius:7px;background:var(--v2-image-workzone)}
  .similarity-debug-asset-copy{display:grid;gap:3px;min-width:0}.similarity-debug-asset-copy b,.similarity-debug-asset-copy small{overflow:hidden;text-overflow:ellipsis}.similarity-debug-asset-copy b{white-space:nowrap}.similarity-debug-asset-copy small{color:var(--v2-muted);font-size:.72rem}
  .similarity-debug-asset-copy small[data-state="unavailable"],.similarity-debug-asset-copy small[data-state="missing_or_stale"]{color:#e3c66f}
  .similarity-debug-settings{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px}.similarity-debug-settings label{display:grid;gap:5px;color:var(--v2-muted);font-size:.75rem}.similarity-debug-settings input,.similarity-debug-settings select{min-width:0;padding:7px 8px;border:1px solid var(--v2-line);border-radius:6px;background:var(--v2-surface);color:var(--v2-text)}
  .similarity-debug-error{color:#ef9a9a}
  .similarity-debug-matrix-wrap{overflow:auto}.similarity-debug-matrix{border-collapse:collapse;width:max-content;min-width:100%;font-size:.75rem}.similarity-debug-matrix th,.similarity-debug-matrix td{border:1px solid var(--v2-line);padding:5px;max-width:150px}.similarity-debug-matrix th{background:var(--v2-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.similarity-debug-matrix td.same{text-align:center;color:var(--v2-muted)}.similarity-debug-matrix td[data-pass="true"]{background:color-mix(in srgb,#3fb950 10%,transparent)}.similarity-debug-matrix td[data-pass="false"]{background:color-mix(in srgb,#f85149 8%,transparent)}.similarity-debug-matrix button{display:grid;gap:2px;width:100%;padding:5px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;cursor:pointer}.similarity-debug-matrix button.active{outline:2px solid var(--v2-accent)}.similarity-debug-matrix button small{color:var(--v2-muted)}
  .similarity-debug-detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:var(--v2-space-3)}.similarity-debug-visual{grid-column:1/-1;min-width:0}.similarity-debug-visual-stage{height:min(62vh,620px);min-height:420px;overflow:hidden}.similarity-debug-visual-stage :global(.v2-compare-component){height:100%}.similarity-debug-kv{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px 12px;align-items:baseline}.similarity-debug-kv span{color:var(--v2-muted)}.similarity-debug-kv b{text-align:right;overflow-wrap:anywhere}.similarity-debug-kv b[data-pass="true"]{color:#8fd694}.similarity-debug-kv b[data-pass="false"]{color:#ef9a9a}
  .similarity-debug-cell-grid{display:grid;grid-template-columns:repeat(var(--columns),minmax(22px,1fr));gap:2px;margin-top:12px;max-height:280px;overflow:auto}.similarity-debug-cell-grid span{display:grid;place-items:center;aspect-ratio:1;background:color-mix(in srgb,var(--v2-accent) var(--change),transparent);font-size:9px;color:var(--v2-text)}
  .similarity-debug-group{display:grid;gap:6px;padding:10px 0;border-bottom:1px solid var(--v2-line)}.similarity-debug-group:last-child{border-bottom:0}.similarity-debug-group>span{color:var(--v2-muted);font-size:.75rem}.similarity-debug-admissions{display:flex;flex-wrap:wrap;gap:6px}.similarity-debug-admissions span{padding:5px 7px;border:1px solid var(--v2-line);border-radius:6px;font-size:.72rem}
  @media(max-width:720px){.similarity-debug-kv{grid-template-columns:1fr}.similarity-debug-kv b{text-align:left}}
</style>
