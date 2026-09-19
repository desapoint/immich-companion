<script lang="ts">
  import V2Badge from '../../../v2/components/V2Badge.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2DuplicateDecisionControls from '../../../v2/components/V2DuplicateDecisionControls.svelte';
  import V2ImageComparison, { type ComparisonMode } from '../../../v2/components/V2ImageComparison.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from '../../../v2/components/V2KeyboardShortcuts.svelte';
  import V2LazyAssetMedia from '../../../v2/components/V2LazyAssetMedia.svelte';
  import V2Section from '../../../v2/components/V2Section.svelte';
  import V2ViewerShell from '../../../v2/components/V2ViewerShell.svelte';
  import DuplicateComparisonDetails from './DuplicateComparisonDetails.svelte';
  import DuplicateComparisonSummary from './DuplicateComparisonSummary.svelte';
  import {
    comparisonMemberData,
    formatSimilarityPercent,
    linkedIntermediateCount,
    similarityValidatedDimensions,
    similarityValidationEvidenceLabel,
    usesBoundedValidation,
    type ComparisonMemberData,
  } from '../../../v2/data/duplicateMember';
  import { stepComparisonTargetId, viewerSelectionTargetId } from '../../../lib/utils/duplicateComparisonNavigation';
  import { duplicateKindLabel } from '../../../v2/data/duplicatePresentation';
  import { libraryData } from '../../../v2/data/currentDataSource.svelte';
  import type {
    AssetRecord,
    DuplicateDecision,
    DuplicateMemberRecord,
    DuplicateSimilarityEvidence,
    MediaResource,
    SimilarityValidationMode,
  } from '../../../v2/data/contracts';
  import { loadLocalChangeDiagnostics, type LocalChangeDiagnostics } from '../../../v2/data/localChangeDiagnostics';
  import { formatByteDifference } from '../../../lib/utils/fileSize';
  import { loadImmichLibraries } from '../../../lib/api/duplicatePolicyApi';

  let {
    open,
    groupTitle,
    groupKind,
    groupSimilarity = null,
    groupMembers = [],
    validationMode = null,
    similarityThreshold = null,
    assetIds = [],
    similarities = {},
    similarityEvidence = {},
    member = $bindable(0),
    reference = $bindable(0),
    decisions = $bindable<Record<string, DuplicateDecision>>({}),
    decisionOptions = [],
    stackLabel = 'Stack',
    stackPrimary = false,
    selectedForReview = false,
    disabled = false,
    canPreviousGroup = false,
    canNextGroup = false,
    groupNavigationLoading = false,
    ongroupnavigate,
    ondecisionchange,
    ondecisionclear,
    onstackprimary,
    onreferencechange,
    onrevalidate,
    onclose,
  }: {
    open: boolean;
    groupTitle: string;
    groupKind: string;
    groupSimilarity?: number | null;
    groupMembers?: DuplicateMemberRecord[];
    validationMode?: SimilarityValidationMode | null;
    similarityThreshold?: number | null;
    assetIds?: string[];
    similarities?: Record<string, number | null>;
    similarityEvidence?: Record<string, DuplicateSimilarityEvidence | null>;
    member?: number;
    reference?: number;
    decisions?: Record<string, DuplicateDecision>;
    decisionOptions?: DuplicateDecision[];
    stackLabel?: string;
    stackPrimary?: boolean;
    selectedForReview?: boolean;
    disabled?: boolean;
    canPreviousGroup?: boolean;
    canNextGroup?: boolean;
    groupNavigationLoading?: boolean;
    ongroupnavigate?: (direction: 'previous' | 'next') => void | Promise<void>;
    ondecisionchange?: (assetId: string, decision: DuplicateDecision) => void;
    ondecisionclear?: (assetId: string) => void;
    onstackprimary?: (assetId: string) => void;
    onreferencechange?: (assetId: string) => Promise<void>;
    onrevalidate?: (assetId: string) => Promise<void>;
    onclose: () => void;
  } = $props();

  const shortcuts: KeyboardShortcut[] = [
    { keys: 'Esc', description: 'Close comparison' },
    { keys: '←', description: 'Previous image in group' },
    { keys: '→', description: 'Next image in group' },
    { keys: ['Shift', '←'], description: 'Previous duplicate group' },
    { keys: ['Shift', '→'], description: 'Next duplicate group' },
    { keys: 'R', description: 'Set current asset as reference' },
    { keys: '1', description: 'Side by side' },
    { keys: '2', description: 'Swipe' },
    { keys: '3', description: 'Transparency' },
    { keys: '4', description: 'Difference' },
    { keys: '5', description: 'Local changes' },
    { keys: '6', description: 'Flicker' },
  ];

  let mode = $state<ComparisonMode>('Side by side');
  let split = $state(50);
  let opacity = $state(50);
  let diffHue = $state(190);
  let diffContrast = $state(180);
  let diffBinary = $state(true);
  let diffTolerance = $state(8);
  let assets = $state<AssetRecord[]>([]);
  let libraryNames = $state<Map<string, string>>(new Map());
  let loading = $state(false);
  let loadError = $state('');
  let loadGeneration = 0;
  let loadedAssetSetKey = '';
  let libraryNamesPromise: Promise<Map<string, string>> | null = null;
  let localDiagnostics = $state<LocalChangeDiagnostics | null>(null);
  let localDiagnosticsLoading = $state(false);
  let localDiagnosticsError = $state('');
  let localDiagnosticsGeneration = 0;
  const localDiagnosticsCache = new Map<string, LocalChangeDiagnostics>();

  const emptyData: ComparisonMemberData = {
    name: 'Unknown asset', source: '—', size: '—', sizeBytes: null, dims: '—', taken: '—',
    codec: 'Unknown type', library: '—', libraryId: null, folder: '—', uploaded: '—', similarity: 'Not calculated',
  };
  const emptyResource: MediaResource = {
    url: '', fallbackUrls: [], mimeType: null, posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null,
  };
  const videoPlaceholder = 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>`);

  function comparisonResource(asset: AssetRecord | undefined): MediaResource {
    if (!asset) return emptyResource;
    if (asset.asset_type === 'VIDEO') return { ...emptyResource, url: videoPlaceholder, mimeType: 'image/svg+xml' };
    return libraryData.media.view(asset);
  }

  function getLibraryNames(): Promise<Map<string, string>> {
    libraryNamesPromise ??= loadImmichLibraries()
      .then((libraries) => new Map(libraries.map((library) => [library.id, library.name])))
      .catch(() => new Map());
    return libraryNamesPromise;
  }

  async function getDetailedAssets(ids: string[]): Promise<AssetRecord[]> {
    const items: AssetRecord[] = [];
    for (let index = 0; index < ids.length; index += 8) {
      const batch = await Promise.all(ids.slice(index, index + 8).map((id) => libraryData.assets.details(id)));
      for (const item of batch) if (item) items.push(item);
    }
    return items;
  }

  function assetSetKey(ids: readonly string[]): string {
    return [...ids].sort().join('\u0000');
  }

  function diagnosticsPairKey(selectedId: string, referenceId: string): string {
    return `${selectedId}\u0000${referenceId}`;
  }

  function identicalDiagnostics(assetId: string): LocalChangeDiagnostics {
    const side = 32;
    return {
      available: true,
      selectedAssetId: assetId,
      referenceAssetId: assetId,
      changedPercent: 0,
      localizedChangedPercent: 0,
      coherentChangedPercent: 0,
      largestChangedRegionPercent: 0,
      substantialRegionCount: 0,
      rows: side,
      columns: side,
      cells: Array.from({ length: side }, () => Array<number>(side).fill(0)),
      source: null,
    };
  }

  function validationModeLabel(value: SimilarityValidationMode | null): string {
    if (value === 'linked') return 'Linked';
    if (value === 'reference') return 'Reference';
    if (value === 'strict') return 'Strict';
    return 'Not available';
  }

  function detailSourceLabel(value: DuplicateSimilarityEvidence['detailSource']): string {
    if (value === 'original') return 'Original';
    if (value === 'transcoded') return 'Full-size conversion';
    if (value === 'preview') return 'Bounded preview';
    return 'Unavailable';
  }

  const activeCount = $derived(assetIds.length);
  const assetById = $derived(new Map(assets.map((asset) => [asset.id, asset])));
  const memberData = $derived(assetIds.map((id) => comparisonMemberData(assetById.get(id), similarities[id] ?? null, libraryNames)));
  const selectedAsset = $derived(assetById.get(assetIds[member]));
  const referenceAsset = $derived(assetById.get(assetIds[reference]));
  const selectedData = $derived(memberData[member] ?? emptyData);
  const referenceData = $derived(memberData[reference] ?? emptyData);
  const selectedResource = $derived(comparisonResource(selectedAsset));
  const referenceResource = $derived(comparisonResource(referenceAsset));
  const decisionKey = $derived(assetIds[member] ?? '');
  const selectedSimilarity = $derived(similarities[decisionKey] ?? null);
  const selectedEvidence = $derived(similarityEvidence[decisionKey] ?? null);
  const selectedGroupMember = $derived(groupMembers.find((candidate) => candidate.asset.id === decisionKey));
  const selectedAdmission = $derived(selectedGroupMember?.admission ?? null);
  const admittedByMember = $derived(groupMembers.find((candidate) => candidate.asset.id === selectedAdmission?.admittedByAssetId));
  const bestGroupMatchMember = $derived(groupMembers.find((candidate) => candidate.asset.id === selectedAdmission?.bestGroupMatchAssetId));
  const boundedValidation = $derived(usesBoundedValidation(selectedEvidence));
  const selectedValidatedDimensions = $derived(similarityValidatedDimensions(selectedEvidence));
  const referenceValidatedDimensions = $derived(similarityValidatedDimensions(selectedEvidence, 'reference'));
  const validationEvidenceLabel = $derived(similarityValidationEvidenceLabel(selectedSimilarity, selectedEvidence));
  const matchLabel = $derived(duplicateKindLabel(groupKind));
  const groupSimilarityLabel = $derived(formatSimilarityPercent(groupSimilarity));
  const groupSimilarityTitle = $derived(validationMode === 'linked' ? 'Group minimum' : 'Group similarity');
  const modeLabel = $derived(validationModeLabel(validationMode));
  const thresholdLabel = $derived(similarityThreshold === null ? 'Unavailable' : formatSimilarityPercent(similarityThreshold));
  const belowThreshold = $derived(similarityThreshold !== null && selectedSimilarity !== null && selectedSimilarity < similarityThreshold);
  const hasIndirectLinkedAdmission = $derived(
    validationMode === 'linked'
      && selectedAdmission !== null
      && selectedAdmission.linkDepth > 0
      && selectedAdmission.admittedByAssetId !== null,
  );
  const intermediateImageCount = $derived(selectedAdmission ? linkedIntermediateCount(selectedAdmission.linkDepth) : 0);
  const showLinkedSummary = $derived(
    hasIndirectLinkedAdmission && (selectedSimilarity === null || belowThreshold),
  );
  const admittedByLabel = $derived(admittedByMember?.asset.original_file_name ?? selectedAdmission?.admittedByAssetId ?? 'Unavailable');
  const bestGroupMatchLabel = $derived(bestGroupMatchMember?.asset.original_file_name ?? selectedAdmission?.bestGroupMatchAssetId ?? 'Unavailable');
  const sizeDifferenceLabel = $derived(formatByteDifference(selectedData.sizeBytes === null || referenceData.sizeBytes === null ? null : selectedData.sizeBytes - referenceData.sizeBytes));
  const sameResolution = $derived(selectedData.dims === referenceData.dims);
  const sameUploadSource = $derived(Boolean(selectedAsset && referenceAsset && !selectedAsset.library_id && !referenceAsset.library_id));
  const sameExternalLibrary = $derived(Boolean(selectedData.libraryId && selectedData.libraryId === referenceData.libraryId));
  const sameSourceCollection = $derived(sameUploadSource || sameExternalLibrary);
  const foldersComparable = $derived(sameSourceCollection && selectedData.folder !== 'Unavailable' && referenceData.folder !== 'Unavailable');
  const sameFolder = $derived(foldersComparable && selectedData.folder === referenceData.folder);
  const folderScopeLabel = $derived(sameUploadSource ? 'Upload folder' : 'External folder');

  function percent(value: number | null): string {
    return formatSimilarityPercent(value);
  }

  function optionalPercent(value: number | null | undefined): string {
    return formatSimilarityPercent(value ?? null);
  }

  const metadataRows = $derived([
    { label: 'File name', selected: selectedData.name, reference: referenceData.name, changed: selectedData.name !== referenceData.name },
    { label: 'Source', selected: selectedData.source, reference: referenceData.source, changed: selectedData.source !== referenceData.source },
    { label: 'Folder', selected: selectedData.folder, reference: referenceData.folder, changed: foldersComparable && !sameFolder },
    { label: 'Format', selected: selectedData.codec, reference: referenceData.codec, changed: selectedData.codec !== referenceData.codec },
    { label: 'File size', selected: selectedData.size, reference: referenceData.size, changed: selectedData.size !== referenceData.size },
    { label: 'Dimensions', selected: selectedData.dims, reference: referenceData.dims, changed: selectedData.dims !== referenceData.dims },
    ...(boundedValidation ? [{
      label: 'Validated at',
      selected: selectedValidatedDimensions ?? 'Unavailable',
      reference: referenceValidatedDimensions ?? 'Unavailable',
      changed: selectedValidatedDimensions !== referenceValidatedDimensions,
    }] : []),
    { label: 'Taken', selected: selectedData.taken, reference: referenceData.taken, changed: selectedData.taken !== referenceData.taken },
    { label: 'Added to Immich', selected: selectedData.uploaded, reference: referenceData.uploaded, changed: selectedData.uploaded !== referenceData.uploaded },
  ]);

  $effect(() => {
    if (!open) return;
    const generation = ++loadGeneration;
    const ids = [...assetIds];
    const requestedAssetSetKey = assetSetKey(ids);
    loading = ids.length > 0 && loadedAssetSetKey !== requestedAssetSetKey;
    loadError = '';
    void (async () => {
      try {
        const [nextAssets, nextLibraryNames] = await Promise.all([getDetailedAssets(ids), getLibraryNames()]);
        if (generation !== loadGeneration) return;
        assets = nextAssets;
        libraryNames = nextLibraryNames;
        loadedAssetSetKey = assetSetKey(nextAssets.map((asset) => asset.id));
      } catch (error) {
        if (generation === loadGeneration) loadError = error instanceof Error ? error.message : 'Could not load comparison assets.';
      } finally {
        if (generation === loadGeneration) loading = false;
      }
    })();
    return () => { loadGeneration += 1; };
  });

  $effect(() => {
    const selectedId = selectedAsset?.id ?? '';
    const referenceId = referenceAsset?.id ?? '';
    const selectedType = selectedAsset?.asset_type;
    const referenceType = referenceAsset?.asset_type;
    const generation = ++localDiagnosticsGeneration;
    const controller = new AbortController();

    localDiagnostics = null;
    localDiagnosticsError = '';
    localDiagnosticsLoading = false;

    if (!open || !selectedId || !referenceId || selectedType !== 'IMAGE' || referenceType !== 'IMAGE') {
      return () => controller.abort();
    }

    const key = diagnosticsPairKey(selectedId, referenceId);
    if (selectedId === referenceId) {
      localDiagnostics = identicalDiagnostics(selectedId);
      return () => controller.abort();
    }

    const cached = localDiagnosticsCache.get(key);
    if (cached) {
      localDiagnostics = cached;
      return () => controller.abort();
    }

    localDiagnosticsLoading = true;
    void (async () => {
      try {
        const result = await loadLocalChangeDiagnostics(selectedId, referenceId, controller.signal);
        if (generation !== localDiagnosticsGeneration) return;
        localDiagnosticsCache.set(key, result);
        localDiagnostics = result;
      } catch (error) {
        if (generation !== localDiagnosticsGeneration || controller.signal.aborted) return;
        localDiagnosticsError = error instanceof Error ? error.message : 'Could not load localized change diagnostics.';
      } finally {
        if (generation === localDiagnosticsGeneration) localDiagnosticsLoading = false;
      }
    })();

    return () => controller.abort();
  });

  function showMemberById(assetId: string) {
    const target = viewerSelectionTargetId(assetIds, assetId);
    member = Math.max(0, assetIds.indexOf(target));
  }
  function showMember(index: number) {
    showMemberById(assetIds[index] ?? '');
  }
  function stepMember(direction: 'previous' | 'next') {
    if (!activeCount) return;
    const target = stepComparisonTargetId(assetIds, assetIds[reference] ?? '', assetIds[member] ?? '', direction);
    member = Math.max(0, assetIds.indexOf(target));
  }
  function prev() { stepMember('previous'); }
  function next() { stepMember('next'); }
  async function navigateGroup(direction: 'previous' | 'next') {
    if (groupNavigationLoading || !ongroupnavigate) return;
    if (direction === 'previous' && !canPreviousGroup) return;
    if (direction === 'next' && !canNextGroup) return;
    await ongroupnavigate(direction);
  }
  function setDecision(decision: DuplicateDecision) {
    if (disabled) return;
    if (decisionKey && decisionOptions.includes(decision)) {
      if (ondecisionchange) ondecisionchange(decisionKey, decision);
      else decisions = { ...decisions, [decisionKey]: decision };
    }
  }
  function clearDecision() {
    if (disabled) return;
    if (decisionKey && decisions[decisionKey]) ondecisionclear?.(decisionKey);
  }
  function setStackPrimary() {
    if (disabled) return;
    if (decisionKey) onstackprimary?.(decisionKey);
  }
  async function setReference() {
    if (disabled || !selectedAsset) return;
    if (onreferencechange) {
      await onreferencechange(selectedAsset.id);
      return;
    }
    reference = member;
    showMember(reference);
  }
  async function revalidate() {
    if (disabled) return;
    const assetId = assetIds[reference];
    if (assetId && onrevalidate) await onrevalidate(assetId);
  }
  function editableTarget(target: EventTarget | null): boolean {
    return target instanceof Element && Boolean(target.closest('input,textarea,select,[contenteditable="true"]'));
  }
  function handleShortcut(event: KeyboardEvent) {
    if (!open || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || editableTarget(event.target)) return;
    if (event.shiftKey && event.key === 'ArrowLeft' && canPreviousGroup && !groupNavigationLoading) { event.preventDefault(); void navigateGroup('previous'); return; }
    if (event.shiftKey && event.key === 'ArrowRight' && canNextGroup && !groupNavigationLoading) { event.preventDefault(); void navigateGroup('next'); return; }
    if (!event.shiftKey && event.key === 'ArrowLeft' && activeCount) { event.preventDefault(); prev(); return; }
    if (!event.shiftKey && event.key === 'ArrowRight' && activeCount) { event.preventDefault(); next(); return; }
    if ((event.key === 'r' || event.key === 'R') && selectedAsset) { event.preventDefault(); void setReference(); return; }
    const modes: Record<string, ComparisonMode> = {
      '1': 'Side by side', '2': 'Swipe', '3': 'Transparency', '4': 'Difference', '5': 'Local changes', '6': 'Flicker',
    };
    const nextMode = modes[event.key];
    if (nextMode) { event.preventDefault(); mode = nextMode; }
  }
</script>

<svelte:window onkeydown={handleShortcut}/>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<div class="v2-compare-header-identity"><V2Button onclick={onclose}>✕</V2Button><b class="v2-compare-group-title" title={groupTitle}>{groupTitle}</b><V2Badge text={matchLabel}/><V2Badge text={`${activeCount} images`}/>{#if selectedForReview}<V2Badge tone="ok" text="Selected for review"/>{/if}{#if boundedValidation}<V2Badge tone="warn" text="Bounded validation"/>{/if}</div><div class="v2-compare-header-actions"><V2Button disabled={!canPreviousGroup||groupNavigationLoading} title="Previous duplicate group (Shift+Left)" onclick={()=>void navigateGroup('previous')}>⇤ Previous group</V2Button><V2Button disabled={!activeCount} onclick={prev}>← Previous image</V2Button><V2Button disabled={!activeCount} onclick={next}>Next image →</V2Button><V2Button disabled={!canNextGroup||groupNavigationLoading} title="Next duplicate group (Shift+Right)" onclick={()=>void navigateGroup('next')}>Next group ⇥</V2Button><V2Button disabled={disabled||!selectedAsset} onclick={()=>void setReference()}>Set as reference</V2Button>{#if onrevalidate}<V2Button disabled={disabled||!assetIds[reference]} onclick={()=>void revalidate()}>Revalidate from reference</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></div>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual">
    {#if loading}<div class="v2-compare-media-status" role="status">Loading comparison media…</div>{:else if loadError}<div class="v2-compare-media-status" role="alert">{loadError}</div>{:else}<V2ImageComparison {selectedResource} {referenceResource} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary bind:diffTolerance {localDiagnostics} {localDiagnosticsLoading} {localDiagnosticsError}/>{/if}
    <div class="v2-filmstrip">{#each assetIds as assetId,index (assetId)}{@const asset=assetById.get(assetId)}{@const data=memberData[index]??emptyData}{@const evidence=similarityEvidence[assetId]??null}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>showMember(index)}>{#if asset}<span class="v2-thumb-media"><V2LazyAssetMedia cacheKey={`duplicate-compare-thumbnail:${asset.id}`} resolve={()=>libraryData.media.thumbnail(asset)} alt={data.name}/></span>{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}{usesBoundedValidation(evidence)?' · Bounded validation':''}</small></button>{/each}</div>
  </section>

  <aside class="v2-compare-data">
    <div class="v2-compare-header-zone">
      <V2Section title="Quick comparison">
        <DuplicateComparisonSummary
          {matchLabel}
          {modeLabel}
          {groupSimilarityTitle}
          {groupSimilarityLabel}
          {selectedData}
          {selectedEvidence}
          {selectedSimilarity}
          {validationEvidenceLabel}
          {boundedValidation}
          {showLinkedSummary}
          {admittedByLabel}
          {selectedAdmission}
          {belowThreshold}
          {thresholdLabel}
          {validationMode}
          {sizeDifferenceLabel}
          {sameResolution}
          {sameSourceCollection}
          {foldersComparable}
          {sameFolder}
        />
      </V2Section>
    </div>

    <DuplicateComparisonDetails
      {selectedData}
      {referenceData}
      {assetIds}
      {metadataRows}
      {hasIndirectLinkedAdmission}
      {selectedAdmission}
      {admittedByMember}
      {admittedByLabel}
      {bestGroupMatchLabel}
      {intermediateImageCount}
      {modeLabel}
      {thresholdLabel}
      {selectedSimilarity}
      {belowThreshold}
      {selectedEvidence}
      {validationEvidenceLabel}
      {boundedValidation}
      {selectedValidatedDimensions}
      {referenceValidatedDimensions}
      {sizeDifferenceLabel}
      {sameResolution}
      {sameSourceCollection}
      {folderScopeLabel}
      {foldersComparable}
      {sameFolder}
      {localDiagnostics}
      {localDiagnosticsLoading}
      {showMemberById}
    />
  </aside></div>
  {#snippet footer()}<span class="v2-compare-footer-label"><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><div class="v2-compare-footer-actions"><div class="v2-compare-footer-decisions"><V2DuplicateDecisionControls decision={decisions[decisionKey]} {stackLabel} isPrimary={stackPrimary} decisions={decisionOptions} {disabled} ondecision={setDecision} onprimary={setStackPrimary}/></div><span class="v2-compare-clear-selection"><V2Button disabled={disabled||!decisions[decisionKey]} onclick={clearDecision}>Clear selection</V2Button></span></div>{/snippet}
</V2ViewerShell>

<style>
  .v2-compare-header-identity,.v2-compare-header-actions{display:flex;align-items:center;gap:var(--v2-space-2);flex-wrap:wrap;min-width:0;max-width:100%}
  .v2-compare-header-identity{flex:1 1 360px}
  .v2-compare-header-actions{flex:0 1 auto;justify-content:flex-end}
  .v2-compare-group-title{display:block;min-width:0;max-width:min(34rem,42vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-compare-footer-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-compare-footer-actions{display:flex;align-items:center;justify-content:flex-end;gap:var(--v2-space-2);flex:0 1 auto;min-width:0;margin-left:auto}
  .v2-compare-footer-decisions{flex:0 1 25rem;width:min(25rem,100%);min-width:min(20rem,100%)}
  .v2-compare-footer-decisions :global(.v2-duplicate-decision-controls){margin-top:0}
  .v2-compare-clear-selection{display:inline-flex;flex:0 0 auto;align-self:center;white-space:nowrap}
  .v2-thumb-media{position:relative;display:block;width:92px;height:92px;overflow:hidden;border-radius:5px}
  .v2-compare-media-status{display:grid;place-items:center;width:100%;height:100%;padding:var(--v2-space-4);color:var(--v2-muted);background:var(--v2-image-workzone);text-align:center}
  .v2-compare-data{display:grid;grid-template-rows:auto minmax(0,1fr);gap:12px;overflow:hidden}
  .v2-compare-header-zone{min-width:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable both-edges}
  @media(max-width:720px){.v2-compare-group-title{max-width:calc(100vw - 8rem)}.v2-compare-header-actions{justify-content:flex-start}.v2-compare-footer-actions{flex:1 1 100%;width:100%}.v2-compare-footer-decisions{flex:1 1 18rem;min-width:0}.v2-compare-data{display:flex;overflow:visible}}
</style>
