<script lang="ts">
  import { onMount } from 'svelte';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2LazyAssetMedia from '../../assets/components/LazyAssetMedia.svelte';
  import SimilarityDebugCompareViewer from './SimilarityDebugCompareViewer.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import type { AssetRecord } from '../../../lib/types/libraryContracts';
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
  let comparisonOpen = $state(false);

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

  function pairKey(left: string, right: string): string {
    return left < right ? `${left}\u0000${right}` : `${right}\u0000${left}`;
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
    if (pair.exclusion_reason === 'invalid_candidate_feature') return 'Invalid feature';
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

  async function analyze(preferredPairKey = ''): Promise<void> {
    if (checkedIds.length < 2) {
      error = 'Choose at least two debug images.';
      return;
    }
    running = true;
    error = '';
    try {
      const nextResponse = await runSimilarityDebug({
        asset_ids: checkedIds,
        similarity_threshold: similarityThreshold,
        validation_mode: validationMode,
        max_link_depth: maxLinkDepth,
        anchor_asset_id: anchorAssetId && checkedIds.includes(anchorAssetId) ? anchorAssetId : null,
        maximum_perceptual_distance: maximumPerceptualDistance,
        maximum_aspect_difference: maximumAspectDifference,
      });
      response = nextResponse;
      const preferredExists = preferredPairKey && nextResponse.pairs.some((candidate) => pairKey(candidate.asset_id_left, candidate.asset_id_right) === preferredPairKey);
      const first = nextResponse.pairs[0];
      activePairKey = preferredExists ? preferredPairKey : first ? pairKey(first.asset_id_left, first.asset_id_right) : '';
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Similarity diagnostics failed.';
      response = null;
      activePairKey = '';
    } finally {
      running = false;
    }
  }

  function openPair(left: string, right: string): void {
    const key = pairKey(left, right);
    if (!pairByKey.has(key)) return;
    activePairKey = key;
    comparisonOpen = true;
  }

  async function setAnchorFromViewer(assetId: string, compareWithAssetId: string): Promise<void> {
    anchorAssetId = assetId;
    const preferredPairKey = pairKey(assetId, compareWithAssetId);
    await analyze(preferredPairKey);
    comparisonOpen = Boolean(activePairKey);
  }

  function pairChangedFromViewer(key: string): void {
    if (!pairByKey.has(key)) return;
    activePairKey = key;
  }

  function anchorSettingChanged(): void {
    if (response) void analyze(activePairKey);
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
          <label>Anchor <select bind:value={anchorAssetId} onchange={anchorSettingChanged}><option value="">Automatic</option>{#each checkedIds as id}<option value={id}>{assetName(id)}</option>{/each}</select></label>
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
                          <button type="button" class:active={activePairKey === pairKey(rowId, columnId)} onclick={() => openPair(rowId, columnId)}>
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

      <SimilarityDebugCompareViewer
        open={comparisonOpen && Boolean(activePair)}
        assetIds={checkedIds}
        {assets}
        pairs={response.pairs}
        pair={activePair}
        {anchorAssetId}
        {validationMode}
        {similarityThreshold}
        onclose={() => comparisonOpen = false}
        onpairchange={pairChangedFromViewer}
        onsetanchor={setAnchorFromViewer}
      />

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
  .similarity-debug-group{display:grid;gap:6px;padding:10px 0;border-bottom:1px solid var(--v2-line)}.similarity-debug-group:last-child{border-bottom:0}.similarity-debug-group>span{color:var(--v2-muted);font-size:.75rem}.similarity-debug-admissions{display:flex;flex-wrap:wrap;gap:6px}.similarity-debug-admissions span{padding:5px 7px;border:1px solid var(--v2-line);border-radius:6px;font-size:.72rem}
</style>
