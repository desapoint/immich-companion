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
  let comparisonReferenceId = $state('');
  let comparisonSelectedId = $state('');

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
    if (!checked && anchorAssetId === assetId) anchorAssetId = '';
    response = null;
    activePairKey = '';
    comparisonOpen = false;
  }

  async function analyze(preferredPairKey = ''): Promise<void> {
    if (checkedIds.length < 2) {
      error = 'Choose at least two debug images.';
      return;
    }
    running = true;
    error = '';
    try {
      const effectiveAnchor = anchorAssetId && checkedIds.includes(anchorAssetId) ? anchorAssetId : checkedIds[0] ?? '';
      anchorAssetId = effectiveAnchor;
      const nextResponse = await runSimilarityDebug({
        asset_ids: checkedIds,
        similarity_threshold: similarityThreshold,
        validation_mode: validationMode,
        max_link_depth: maxLinkDepth,
        anchor_asset_id: effectiveAnchor || null,
        maximum_perceptual_distance: maximumPerceptualDistance,
        maximum_aspect_difference: maximumAspectDifference,
      });
      response = nextResponse;
      const preferredExists = preferredPairKey && nextResponse.pairs.some((candidate) => pairKey(candidate.asset_id_left, candidate.asset_id_right) === preferredPairKey);
      const anchorPair = nextResponse.pairs.find((candidate) => candidate.asset_id_left === effectiveAnchor || candidate.asset_id_right === effectiveAnchor);
      const first = nextResponse.pairs[0];
      activePairKey = preferredExists
        ? preferredPairKey
        : anchorPair
          ? pairKey(anchorPair.asset_id_left, anchorPair.asset_id_right)
          : first
            ? pairKey(first.asset_id_left, first.asset_id_right)
            : '';
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Similarity diagnostics failed.';
      response = null;
      activePairKey = '';
    } finally {
      running = false;
    }
  }

  function openPair(referenceAssetId: string, selectedAssetId: string): void {
    const key = pairKey(referenceAssetId, selectedAssetId);
    if (!pairByKey.has(key)) return;
    activePairKey = key;
    comparisonReferenceId = referenceAssetId;
    comparisonSelectedId = selectedAssetId;
    comparisonOpen = true;
  }

  function openAgainstAnchor(assetId: string): void {
    if (!response || !anchorAssetId || assetId === anchorAssetId || !selected.has(assetId)) return;
    openPair(anchorAssetId, assetId);
  }

  async function setAnchorFromList(assetId: string): Promise<void> {
    if (!selected.has(assetId)) return;
    const hadResponse = Boolean(response);
    const previousTarget = comparisonSelectedId && comparisonSelectedId !== assetId && selected.has(comparisonSelectedId)
      ? comparisonSelectedId
      : checkedIds.find((id) => id !== assetId) ?? '';
    anchorAssetId = assetId;
    if (!hadResponse) return;
    const preferredPairKey = previousTarget ? pairKey(assetId, previousTarget) : '';
    await analyze(preferredPairKey);
    if (comparisonOpen && previousTarget && pairByKey.has(preferredPairKey)) {
      comparisonReferenceId = assetId;
      comparisonSelectedId = previousTarget;
    }
  }

  async function setAnchorFromViewer(assetId: string, compareWithAssetId: string): Promise<void> {
    anchorAssetId = assetId;
    const preferredPairKey = pairKey(assetId, compareWithAssetId);
    await analyze(preferredPairKey);
    comparisonReferenceId = assetId;
    comparisonSelectedId = compareWithAssetId;
    comparisonOpen = Boolean(activePairKey);
  }

  function pairChangedFromViewer(key: string, referenceAssetId: string, selectedAssetId: string): void {
    if (!pairByKey.has(key)) return;
    activePairKey = key;
    comparisonReferenceId = referenceAssetId;
    comparisonSelectedId = selectedAssetId;
  }

  function anchorSettingChanged(): void {
    if (anchorAssetId) {
      void setAnchorFromList(anchorAssetId);
      return;
    }
    if (response) void analyze(activePairKey);
  }

  function remove(assetId: string): void {
    removeSimilarityDebugAsset(assetId);
    response = null;
    activePairKey = '';
    comparisonOpen = false;
    if (anchorAssetId === assetId) anchorAssetId = '';
    void refreshBasket();
  }

  function clear(): void {
    clearSimilarityDebugAssets();
    assetIds = [];
    assets = [];
    selected = new Set();
    response = null;
    activePairKey = '';
    comparisonOpen = false;
    comparisonReferenceId = '';
    comparisonSelectedId = '';
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
    <V2Section title="Debug group">
      {#if loadingAssets}
        <V2Card><span class="v2-muted">Loading debug images…</span></V2Card>
      {:else if !assetIds.length}
        <V2Card><span class="v2-muted">Add images from Assets Viewer or Duplicate comparison, then return here to inspect them.</span></V2Card>
      {:else}
        <V2Card>
          <div class="similarity-debug-group-toolbar">
            <div>
              <b>{checkedIds.length} of {assetIds.length} images in this debug group</b>
              <span class="v2-small v2-muted">Select the images you want analyzed. Choose one as the anchor, then click another selected image to compare it against the anchor.</span>
            </div>
            {#if anchorAssetId}
              <V2Badge tone="ok" text={`Anchor: ${assetName(anchorAssetId)}`}/>
            {:else}
              <V2Badge text="Anchor: automatic on analyze"/>
            {/if}
          </div>

          <div class="similarity-debug-assets">
            {#each assetIds as assetId (assetId)}
              {@const asset = assetById.get(assetId)}
              {@const evidence = resultAssetById.get(assetId)}
              {@const inGroup = selected.has(assetId)}
              {@const isAnchor = anchorAssetId === assetId}
              <article class="similarity-debug-asset-tile" class:selected={inGroup} class:anchor={isAnchor}>
                <div class="similarity-debug-tile-top">
                  <label class="similarity-debug-selection-control" title={inGroup ? 'Remove from debug group' : 'Add to debug group'}>
                    <input type="checkbox" checked={inGroup} onchange={(event) => toggle(assetId, event.currentTarget.checked)}>
                    <span>{inGroup ? 'Selected' : 'Select'}</span>
                  </label>
                  {#if isAnchor}<V2Badge tone="ok" text="Anchor"/>{/if}
                </div>

                <button
                  type="button"
                  class="similarity-debug-tile-media"
                  disabled={!response || !inGroup || isAnchor}
                  title={response && inGroup && !isAnchor ? `Compare ${assetName(assetId)} to anchor` : assetName(assetId)}
                  onclick={() => openAgainstAnchor(assetId)}
                >
                  {#if asset}<V2LazyAssetMedia cacheKey={`similarity-debug:${asset.id}`} resolve={() => libraryData.media.thumbnail(asset)} alt={asset.original_file_name}/>{/if}
                </button>

                <div class="similarity-debug-asset-copy">
                  <b title={asset?.original_file_name ?? assetId}>{asset?.original_file_name ?? assetId}</b>
                  <small>{asset?.width ?? '—'} × {asset?.height ?? '—'}</small>
                  {#if evidence}
                    <small data-state={evidence.evidence_state}>{evidence.evidence_state === 'current' ? `Current · ${evidence.fingerprint_origin ?? 'unknown source'}` : evidence.reason ?? evidence.evidence_state}</small>
                  {/if}
                </div>

                <div class="similarity-debug-tile-actions">
                  {#if isAnchor}
                    <span class="similarity-debug-anchor-status v2-small v2-muted">Comparison anchor</span>
                  {:else}
                    <div class="similarity-debug-action-anchor">
                      <V2Button block disabled={!inGroup || running} onclick={() => void setAnchorFromList(assetId)}>Set as anchor</V2Button>
                    </div>
                  {/if}
                  {#if response && inGroup && !isAnchor}
                    <div class="similarity-debug-action-compare">
                      <V2Button block variant="primary" onclick={() => openAgainstAnchor(assetId)}>Compare</V2Button>
                    </div>
                  {/if}
                  <div class="similarity-debug-action-remove" class:wide={!response || !inGroup || isAnchor}>
                    <V2Button block onclick={() => remove(assetId)}>Remove</V2Button>
                  </div>
                </div>
              </article>
            {/each}
          </div>
        </V2Card>
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
        referenceAssetId={comparisonReferenceId}
        selectedAssetId={comparisonSelectedId}
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
  .similarity-debug-group-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px;min-width:0;flex-wrap:wrap}.similarity-debug-group-toolbar>div{display:grid;gap:3px;min-width:0;flex:1 1 360px}.similarity-debug-group-toolbar :global(.v2-badge){max-width:min(100%,360px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .similarity-debug-assets{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:var(--v2-space-3);align-items:stretch}
  .similarity-debug-asset-tile{position:relative;display:grid;grid-template-rows:auto minmax(150px,1fr) auto auto;gap:8px;min-width:0;overflow:hidden;padding:8px;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface)}
  .similarity-debug-asset-tile.selected{outline:1px solid color-mix(in srgb,var(--v2-accent) 45%,transparent)}
  .similarity-debug-asset-tile.anchor{outline:2px solid var(--v2-accent)}
  .similarity-debug-tile-top{display:flex;align-items:center;justify-content:space-between;gap:7px;min-width:0}
  .similarity-debug-tile-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;align-items:stretch;min-width:0}
  .similarity-debug-action-anchor,.similarity-debug-anchor-status{grid-column:1/-1}
  .similarity-debug-action-compare,.similarity-debug-action-remove{min-width:0}
  .similarity-debug-action-remove.wide{grid-column:1/-1}
  .similarity-debug-anchor-status{display:flex;align-items:center;min-height:34px;padding:0 2px}
  .similarity-debug-tile-actions :global(.v2-button){width:100%;min-width:0;max-width:100%;padding:7px 8px;white-space:normal;line-height:1.15;text-align:center}
  .similarity-debug-selection-control{display:flex;align-items:center;gap:6px;min-width:0;font-size:.72rem;color:var(--v2-muted);cursor:pointer}
  .similarity-debug-tile-media{position:relative;display:block;width:100%;min-height:150px;padding:0;overflow:hidden;border:0;border-radius:7px;background:var(--v2-image-workzone);cursor:pointer}
  .similarity-debug-tile-media:disabled{cursor:default;opacity:.72}
  .similarity-debug-tile-media :global(img),.similarity-debug-tile-media :global(video){width:100%;height:100%;object-fit:cover}
  .similarity-debug-asset-copy{display:grid;gap:3px;min-width:0}.similarity-debug-asset-copy b,.similarity-debug-asset-copy small{overflow:hidden;text-overflow:ellipsis}.similarity-debug-asset-copy b{white-space:nowrap}.similarity-debug-asset-copy small{color:var(--v2-muted);font-size:.72rem}
  .similarity-debug-asset-copy small[data-state="unavailable"],.similarity-debug-asset-copy small[data-state="missing_or_stale"]{color:#e3c66f}
  .similarity-debug-settings{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px}.similarity-debug-settings label{display:grid;gap:5px;color:var(--v2-muted);font-size:.75rem}.similarity-debug-settings input,.similarity-debug-settings select{min-width:0;padding:7px 8px;border:1px solid var(--v2-line);border-radius:6px;background:var(--v2-surface);color:var(--v2-text)}
  .similarity-debug-error{color:#ef9a9a}
  .similarity-debug-matrix-wrap{overflow:auto}.similarity-debug-matrix{border-collapse:collapse;width:max-content;min-width:100%;font-size:.75rem}.similarity-debug-matrix th,.similarity-debug-matrix td{border:1px solid var(--v2-line);padding:5px;max-width:150px}.similarity-debug-matrix th{background:var(--v2-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.similarity-debug-matrix td.same{text-align:center;color:var(--v2-muted)}.similarity-debug-matrix td[data-pass="true"]{background:color-mix(in srgb,#3fb950 10%,transparent)}.similarity-debug-matrix td[data-pass="false"]{background:color-mix(in srgb,#f85149 8%,transparent)}.similarity-debug-matrix button{display:grid;gap:2px;width:100%;padding:5px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;cursor:pointer}.similarity-debug-matrix button.active{outline:2px solid var(--v2-accent)}.similarity-debug-matrix button small{color:var(--v2-muted)}
  .similarity-debug-group{display:grid;gap:6px;padding:10px 0;border-bottom:1px solid var(--v2-line)}.similarity-debug-group:last-child{border-bottom:0}.similarity-debug-group>span{color:var(--v2-muted);font-size:.75rem}.similarity-debug-admissions{display:flex;flex-wrap:wrap;gap:6px}.similarity-debug-admissions span{padding:5px 7px;border:1px solid var(--v2-line);border-radius:6px;font-size:.72rem}
  @media(max-width:560px){
    .similarity-debug-assets{grid-template-columns:1fr}
    .similarity-debug-group-toolbar :global(.v2-badge){max-width:100%}
  }
</style>
