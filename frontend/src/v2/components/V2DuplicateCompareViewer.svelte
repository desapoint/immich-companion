<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2DuplicateDecisionControls from './V2DuplicateDecisionControls.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2LazyAssetMedia from './V2LazyAssetMedia.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import {
    comparisonMemberData,
    formatSimilarityPercent,
    similarityValidatedDimensions,
    similarityValidationEvidenceLabel,
    usesBoundedValidation,
    type ComparisonMemberData,
  } from '../data/duplicateMember';
  import { stepComparisonTargetId, viewerSelectionTargetId } from '../../lib/utils/duplicateComparisonNavigation';
  import { duplicateKindLabel } from '../data/duplicatePresentation';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type {
    AssetRecord,
    DuplicateDecision,
    DuplicateMemberRecord,
    DuplicateSimilarityEvidence,
    MediaResource,
    SimilarityValidationMode,
  } from '../data/contracts';
  import { loadLocalChangeDiagnostics, type LocalChangeDiagnostics } from '../data/localChangeDiagnostics';
  import { formatByteDifference } from '../../lib/utils/fileSize';
  import { loadImmichLibraries } from '../../lib/api/duplicatePolicyApi';

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
    disabled = false,
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
    disabled?: boolean;
    ondecisionchange?: (assetId: string, decision: DuplicateDecision) => void;
    ondecisionclear?: (assetId: string) => void;
    onstackprimary?: (assetId: string) => void;
    onreferencechange?: (assetId: string) => Promise<void>;
    onrevalidate?: (assetId: string) => Promise<void>;
    onclose: () => void;
  } = $props();

  const shortcuts: KeyboardShortcut[] = [
    { keys: 'Esc', description: 'Close comparison' },
    { keys: '←', description: 'Previous group member' },
    { keys: '→', description: 'Next group member' },
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
      && selectedAdmission.linkDepth > 1
      && selectedAdmission.admittedByAssetId !== null,
  );
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

  function showMember(index: number) {
    const target = viewerSelectionTargetId(assetIds, assetIds[index] ?? '');
    member = Math.max(0, assetIds.indexOf(target));
  }
  function stepMember(direction: 'previous' | 'next') {
    if (!activeCount) return;
    const target = stepComparisonTargetId(assetIds, assetIds[reference] ?? '', assetIds[member] ?? '', direction);
    member = Math.max(0, assetIds.indexOf(target));
  }
  function prev() { stepMember('previous'); }
  function next() { stepMember('next'); }
  function setDecision(decision: DuplicateDecision) {
    if (disabled) return;
    if (decisionKey && decisionOptions.includes(decision)) {
      decisions = { ...decisions, [decisionKey]: decision };
      ondecisionchange?.(decisionKey, decision);
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
    if (event.key === 'ArrowLeft' && activeCount) { event.preventDefault(); prev(); return; }
    if (event.key === 'ArrowRight' && activeCount) { event.preventDefault(); next(); return; }
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
  {#snippet header()}<div class="v2-compare-header-identity"><V2Button onclick={onclose}>✕</V2Button><b class="v2-compare-group-title" title={groupTitle}>{groupTitle}</b><V2Badge text={matchLabel}/><V2Badge text={`${activeCount} images`}/>{#if boundedValidation}<V2Badge tone="warn" text="Bounded validation"/>{/if}</div><div class="v2-compare-header-actions"><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={disabled||!selectedAsset} onclick={()=>void setReference()}>Set as reference</V2Button>{#if onrevalidate}<V2Button disabled={disabled||!assetIds[reference]} onclick={()=>void revalidate()}>Revalidate from reference</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></div>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual">
    {#if loading}<div class="v2-compare-media-status" role="status">Loading comparison media…</div>{:else if loadError}<div class="v2-compare-media-status" role="alert">{loadError}</div>{:else}<V2ImageComparison {selectedResource} {referenceResource} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary bind:diffTolerance {localDiagnostics} {localDiagnosticsLoading} {localDiagnosticsError}/>{/if}
    <div class="v2-filmstrip">{#each assetIds as assetId,index (assetId)}{@const asset=assetById.get(assetId)}{@const data=memberData[index]??emptyData}{@const evidence=similarityEvidence[assetId]??null}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>showMember(index)}>{#if asset}<span class="v2-thumb-media"><V2LazyAssetMedia cacheKey={`duplicate-compare-thumbnail:${asset.id}`} resolve={()=>libraryData.media.thumbnail(asset)} alt={data.name}/></span>{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}{usesBoundedValidation(evidence)?' · Bounded validation':''}</small></button>{/each}</div>
  </section>

  <aside class="v2-compare-data">
    <div class="v2-compare-header-zone">
      <V2Section title="Quick comparison">
        <V2Card>
          <div class="v2-compare-summary">
            <V2Inline justify="between"><span>Match type</span><b>{matchLabel}</b></V2Inline>
            <V2Inline justify="between"><span>Validation mode</span><b>{modeLabel}</b></V2Inline>
            <V2Inline justify="between"><span>{groupSimilarityTitle}</span><b>{groupSimilarityLabel}</b></V2Inline>
            <V2Inline justify="between"><span>Similarity to reference</span><b class:warn-value={belowThreshold}>{selectedData.similarity}</b></V2Inline>

            {#if selectedEvidence}
              <div class="v2-compare-score-line" aria-label="Similarity score components">
                <span>Structure <b>{percent(selectedEvidence.structuralPercent)}</b></span>
                <span>Hash <b>{percent(selectedEvidence.perceptualPercent)}</b></span>
                <span>Color <b>{percent(selectedEvidence.colorPercent)}</b></span>
              </div>
            {:else}
              <V2Inline justify="between"><span>Visual score details</span><b>Not calculated</b></V2Inline>
            {/if}

            {#if showLinkedSummary && selectedAdmission}
              <div class="v2-compare-link-summary">
                <b>Included through {admittedByLabel}</b>
                <span>{formatSimilarityPercent(selectedAdmission.admissionSimilarityPercent)} admission similarity</span>
              </div>
            {/if}

            <div class="v2-compare-chips">
              {#if boundedValidation}<span class="v2-compare-chip warn">Bounded validation</span>{/if}
              {#if similarityThreshold !== null && selectedSimilarity !== null}
                <span class="v2-compare-chip" class:warn={belowThreshold} class:ok={!belowThreshold}>{belowThreshold?'Below':'Above'} {thresholdLabel} threshold</span>
              {:else if validationMode === 'linked' && selectedSimilarity === null}
                <span class="v2-compare-chip warn">Reference score unavailable</span>
              {/if}
              <span class="v2-compare-chip">{sizeDifferenceLabel}</span>
              <span class="v2-compare-chip" class:warn={!sameResolution} class:ok={sameResolution}>{sameResolution?'Same':'Different'} resolution</span>
              {#if sameSourceCollection}
                <span class="v2-compare-chip" class:warn={!foldersComparable||!sameFolder} class:ok={foldersComparable&&sameFolder}>{!foldersComparable?'Folder unavailable':sameFolder?'Same folder':'Different folder'}</span>
              {/if}
            </div>
          </div>
        </V2Card>
      </V2Section>
    </div>

    <div class="v2-compare-detail-scroll">
      <details class="v2-compare-detail v2-compare-metadata-detail" open>
        <summary>Metadata side by side</summary>
        <div class="v2-compare-detail-body v2-compare-metadata-body">
          <div class="v2-compare-grid" role="table" aria-label="Selected and reference asset metadata">
            <div class="v2-compare-grid-heading v2-compare-grid-property" role="columnheader">Property</div>
            <div class="v2-compare-grid-heading" role="columnheader"><span>Selected</span><small title={selectedData.name}>{selectedData.name}</small></div>
            <div class="v2-compare-grid-heading" role="columnheader"><span>Reference</span><small title={referenceData.name}>{referenceData.name}</small></div>
            {#each metadataRows as row (row.label)}
              <div class="v2-compare-grid-label" role="rowheader">{row.label}</div>
              <div class:changed={row.changed} class="v2-compare-grid-value" role="cell">{row.selected}</div>
              <div class:changed={row.changed} class="v2-compare-grid-value" role="cell">{row.reference}</div>
            {/each}
          </div>
        </div>
      </details>

      {#if hasIndirectLinkedAdmission && selectedAdmission}
        <details class="v2-compare-detail">
          <summary>Why is this image in the group?</summary>
          <div class="v2-compare-detail-body">
            <div class="v2-compare-key-values">
              <span>Validation mode</span><b>{modeLabel}</b>
              <span>Threshold</span><b>{thresholdLabel}</b>
              <span>Similarity to reference</span><b class:warn-value={belowThreshold}>{selectedData.similarity}</b>
              <span>Admitted through</span><b class="v2-compare-link-value">{admittedByLabel}</b>
              <span>Admission similarity</span><b>{formatSimilarityPercent(selectedAdmission.admissionSimilarityPercent)}</b>
              <span>Link depth</span><b>{selectedAdmission.linkDepth}</b>
              <span>Best group match</span><b class="v2-compare-link-value">{bestGroupMatchLabel}</b>
              <span>Best group similarity</span><b>{formatSimilarityPercent(selectedAdmission.bestGroupMatchSimilarityPercent)}</b>
            </div>
            <p class="v2-compare-detail-note">“Admitted through” is the comparison edge that allowed this member into a linked group. “Best group match” is the strongest known relationship in the group and can be a different image.</p>
          </div>
        </details>
      {/if}

      <details class="v2-compare-detail">
        <summary>Similarity &amp; validation details</summary>
        <div class="v2-compare-detail-body">
          <div class="v2-compare-key-values">
            <span>Similarity to reference</span><b>{selectedData.similarity}</b>
            {#if selectedEvidence}
              <span>Structure <small class="v2-muted">· 65% weight</small></span><b>{percent(selectedEvidence.structuralPercent)}</b>
              <span>Perceptual hash <small class="v2-muted">· 25% weight</small></span><b>{percent(selectedEvidence.perceptualPercent)}</b>
              <span>Color <small class="v2-muted">· 10% weight</small></span><b>{percent(selectedEvidence.colorPercent)}</b>
              <span>Validation evidence</span><b>{validationEvidenceLabel ?? 'Unavailable'}</b>
              {#if selectedEvidence.detailChangedPercent!==null&&selectedEvidence.detailChangedPercent!==undefined}
                <span>Detail changed area <small class="v2-muted">· sampled</small></span><b>{percent(selectedEvidence.detailChangedPercent)}</b>
                <span>Detail evidence</span><b>{detailSourceLabel(selectedEvidence.detailSource)}</b>
              {/if}
              <span>Selected original dimensions</span><b>{selectedData.dims}</b>
              <span>Reference original dimensions</span><b>{referenceData.dims}</b>
              {#if selectedValidatedDimensions || referenceValidatedDimensions}
                <span>Validated at</span><b>{selectedValidatedDimensions ?? 'Unavailable'}</b>
                <span>Reference validated at</span><b>{referenceValidatedDimensions ?? 'Unavailable'}</b>
              {/if}
            {:else}
              <span>Visual score details</span><b>Not calculated</b>
            {/if}
          </div>
          {#if boundedValidation}
            <p class="v2-compare-detail-note">At least one side cannot be fully decoded within Companion's 64-megapixel safety limit, or its original/full-size detail evidence was unavailable. Similarity therefore uses bounded Immich-generated visual evidence. The metadata table shows original dimensions and the actual rendition dimensions used when they are known. Bounded validation is review evidence, not full-resolution or destructive proof.</p>
          {/if}
          {#if selectedEvidence?.detailChangedPercent!==null&&selectedEvidence?.detailChangedPercent!==undefined}
            <p class="v2-compare-detail-note">The final similarity includes this candidate detail check. Difference shows displayed-pixel changes; Local changes shows the validator grid.</p>
          {/if}
        </div>
      </details>

      <details class="v2-compare-detail">
        <summary>Local-change validator</summary>
        <div class="v2-compare-detail-body">
          <div class="v2-compare-key-values">
            <span>Peak local change <small class="v2-muted">· validator</small></span><b>{localDiagnosticsLoading?'Calculating…':localDiagnostics?.available?optionalPercent(localDiagnostics.localizedChangedPercent):'Unavailable'}</b>
            <span>Coherent changed area <small class="v2-muted">· validator</small></span><b>{localDiagnosticsLoading?'Calculating…':localDiagnostics?.available?optionalPercent(localDiagnostics.coherentChangedPercent):'Unavailable'}</b>
            <span>Largest changed region <small class="v2-muted">· validator</small></span><b>{localDiagnosticsLoading?'Calculating…':localDiagnostics?.available?optionalPercent(localDiagnostics.largestChangedRegionPercent):'Unavailable'}</b>
            <span>Substantial regions <small class="v2-muted">· validator</small></span><b>{localDiagnosticsLoading?'Calculating…':localDiagnostics?.available?(localDiagnostics.substantialRegionCount??'—'):'Unavailable'}</b>
          </div>
          <p class="v2-compare-detail-note">The detail validator uses this local grid and coherent-region topology when scoring candidate similarity. The Local changes view explains that evidence; it is not a separate mismatch rule.</p>
        </div>
      </details>

      <details class="v2-compare-detail">
        <summary>File differences</summary>
        <div class="v2-compare-detail-body">
          <div class="v2-compare-key-values">
            <span>File size difference</span><b>{sizeDifferenceLabel}</b>
            <span>Resolution</span><b>{sameResolution?'Same':'Different'}</b>
            {#if sameSourceCollection}<span>{folderScopeLabel}</span><b>{!foldersComparable?'Unavailable':sameFolder?'Same':'Different'}</b>{/if}
            <span>Difference source</span><b>Layered displayed pixels</b>
          </div>
        </div>
      </details>

      {#if hasIndirectLinkedAdmission && selectedAdmission}
        <details class="v2-compare-detail">
          <summary>Technical linked data</summary>
          <div class="v2-compare-detail-body">
            <div class="v2-compare-key-values">
              <span>Model version</span><b class="v2-compare-technical-value">{selectedAdmission.modelVersion}</b>
              <span>Feature version</span><b>{selectedAdmission.featureVersion}</b>
              <span>Comparison version</span><b>{selectedAdmission.comparisonVersion}</b>
              <span>Config fingerprint</span><b class="v2-compare-technical-value">{selectedAdmission.configFingerprint}</b>
            </div>
          </div>
        </details>
      {/if}
    </div>
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
  .v2-compare-detail-scroll{display:flex;flex-direction:column;align-items:stretch;gap:12px;min-width:0;min-height:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable both-edges}
  .v2-compare-detail-scroll>.v2-compare-detail{flex:0 0 auto}
  .v2-compare-summary{display:grid;gap:var(--v2-space-2);min-width:0}
  .v2-compare-score-line{display:flex;gap:6px 10px;flex-wrap:wrap;padding-top:8px;border-top:1px solid var(--v2-line);color:var(--v2-muted);font-size:11px}
  .v2-compare-score-line b{color:var(--v2-text)}
  .v2-compare-link-summary{display:grid;gap:2px;padding:8px 9px;border:1px solid color-mix(in srgb,var(--v2-accent) 35%,var(--v2-line));border-radius:8px;background:color-mix(in srgb,var(--v2-accent) 8%,transparent);font-size:11px;overflow-wrap:anywhere}
  .v2-compare-link-summary span{color:var(--v2-muted)}
  .v2-compare-chips{display:flex;gap:6px;flex-wrap:wrap}
  .v2-compare-chip{display:inline-flex;align-items:center;min-width:0;padding:3px 7px;border:1px solid var(--v2-line);border-radius:999px;background:color-mix(in srgb,var(--v2-surface) 82%,var(--v2-accent-2));color:var(--v2-muted);font-size:10px;line-height:1.2}
  .v2-compare-chip.ok{border-color:color-mix(in srgb,#38a169 55%,var(--v2-line));color:#8be0ad}
  .v2-compare-chip.warn{border-color:color-mix(in srgb,#c59a35 60%,var(--v2-line));color:#e3c66f}
  .warn-value{color:#e3c66f}
  .v2-compare-detail{min-width:0;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface);overflow:hidden}
  .v2-compare-detail summary{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;padding:10px 11px;cursor:pointer;color:var(--v2-text);font-weight:700;list-style:none;user-select:none}
  .v2-compare-detail summary::-webkit-details-marker{display:none}
  .v2-compare-detail summary::after{content:'▸';flex:0 0 auto;color:var(--v2-muted);transition:transform .12s ease}
  .v2-compare-detail[open] summary::after{transform:rotate(90deg)}
  .v2-compare-detail[open] summary{border-bottom:1px solid var(--v2-line)}
  .v2-compare-detail-body{min-width:0;padding:10px 11px}
  .v2-compare-key-values{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px 10px;align-items:baseline;min-width:0}
  .v2-compare-key-values>span{min-width:0;color:var(--v2-muted);overflow-wrap:anywhere}
  .v2-compare-key-values>b{min-width:0;max-width:13rem;color:var(--v2-text);text-align:right;overflow-wrap:anywhere}
  .v2-compare-link-value{color:var(--v2-accent)!important}
  .v2-compare-detail-note{margin:10px 0 0;padding:8px 9px;border-left:3px solid color-mix(in srgb,var(--v2-accent) 45%,var(--v2-line));background:color-mix(in srgb,var(--v2-accent) 6%,transparent);color:var(--v2-muted);font-size:11px;line-height:1.45}
  .v2-compare-metadata-body{overflow:hidden}
  .v2-compare-metadata-body :global(.v2-compare-grid){width:100%;max-width:100%;overflow:hidden}
  .v2-compare-technical-value{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10px;word-break:break-all}
  @media(max-width:720px){.v2-compare-group-title{max-width:calc(100vw - 8rem)}.v2-compare-header-actions{justify-content:flex-start}.v2-compare-footer-actions{flex:1 1 100%;width:100%}.v2-compare-footer-decisions{flex:1 1 18rem;min-width:0}.v2-compare-data{display:flex;overflow:visible}.v2-compare-header-zone,.v2-compare-detail-scroll{overflow:visible;scrollbar-gutter:auto}.v2-compare-detail-scroll>.v2-compare-detail{flex:0 0 auto}.v2-compare-key-values{grid-template-columns:1fr}.v2-compare-key-values>b{text-align:left;max-width:none}}
</style>