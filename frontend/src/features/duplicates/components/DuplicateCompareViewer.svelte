<script lang="ts">
  import V2ImageComparison, { type ComparisonMode } from '../../../v2/components/V2ImageComparison.svelte';
  import V2LazyAssetMedia from '../../../v2/components/V2LazyAssetMedia.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2ViewerShell from '../../../v2/components/V2ViewerShell.svelte';
  import DuplicateComparisonDetails from './DuplicateComparisonDetails.svelte';
  import DuplicateComparisonSummary from './DuplicateComparisonSummary.svelte';
  import DuplicateComparisonHeader from './DuplicateComparisonHeader.svelte';
  import DuplicateComparisonFooter from './DuplicateComparisonFooter.svelte';
  import {
    comparisonMemberData,
    formatSimilarityPercent,
    linkedIntermediateCount,
    similarityValidatedDimensions,
    similarityValidationEvidenceLabel,
    usesBoundedValidation,
    type ComparisonMemberData,
  } from '../types/duplicateMember';
  import { stepComparisonTargetId, viewerSelectionTargetId } from '../../../lib/utils/duplicateComparisonNavigation';
  import { duplicateKindLabel } from '../utils/duplicatePresentation';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import type {
    AssetRecord,
    DuplicateDecision,
    DuplicateMemberRecord,
    DuplicateSimilarityEvidence,
    SimilarityValidationMode,
  } from '../types/contracts';
  import { formatByteDifference } from '../../../lib/utils/fileSize';
  import { DuplicateComparisonDataController } from '../state/duplicateComparisonData.svelte';

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


  let mode = $state<ComparisonMode>('Side by side');
  let split = $state(50);
  let opacity = $state(50);
  let diffHue = $state(190);
  let diffContrast = $state(180);
  let diffBinary = $state(true);
  let diffTolerance = $state(8);
  const comparisonData = new DuplicateComparisonDataController();

  const emptyData: ComparisonMemberData = {
    name: 'Unknown asset', source: '—', size: '—', sizeBytes: null, dims: '—', taken: '—',
    codec: 'Unknown type', library: '—', libraryId: null, folder: '—', uploaded: '—', similarity: 'Not calculated',
  };

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
  const assetById = $derived(new Map(comparisonData.assets.map((asset) => [asset.id, asset])));
  const memberData = $derived(assetIds.map((id) => comparisonMemberData(assetById.get(id), similarities[id] ?? null, comparisonData.libraryNames)));
  const selectedAsset = $derived(assetById.get(assetIds[member]));
  const referenceAsset = $derived(assetById.get(assetIds[reference]));
  const selectedData = $derived(memberData[member] ?? emptyData);
  const referenceData = $derived(memberData[reference] ?? emptyData);
  const selectedResource = $derived(comparisonData.resource(selectedAsset));
  const referenceResource = $derived(comparisonData.resource(referenceAsset));
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

  $effect(() => { void comparisonData.load(assetIds, open); return () => comparisonData.invalidate(); });
  $effect(() => { void comparisonData.loadDiagnostics(selectedAsset, referenceAsset, open); return () => comparisonData.invalidate(); });

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
  {#snippet header()}<DuplicateComparisonHeader {groupTitle} {matchLabel} {activeCount} {selectedForReview} {boundedValidation} {canPreviousGroup} {canNextGroup} {groupNavigationLoading} {disabled} hasSelectedAsset={Boolean(selectedAsset)} hasReference={Boolean(assetIds[reference])} {onclose} onpreviousgroup={()=>void navigateGroup('previous')} onprevious={prev} onnext={next} onnextgroup={()=>void navigateGroup('next')} onreference={()=>void setReference()} onrevalidate={onrevalidate?()=>void revalidate():undefined}/>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual">
    {#if comparisonData.loading}<div class="v2-compare-media-status" role="status">Loading comparison media…</div>{:else if comparisonData.loadError}<div class="v2-compare-media-status" role="alert">{comparisonData.loadError}</div>{:else}<V2ImageComparison {selectedResource} {referenceResource} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary bind:diffTolerance localDiagnostics={comparisonData.localDiagnostics} localDiagnosticsLoading={comparisonData.localDiagnosticsLoading} localDiagnosticsError={comparisonData.localDiagnosticsError}/>{/if}
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
      localDiagnostics={comparisonData.localDiagnostics}
      localDiagnosticsLoading={comparisonData.localDiagnosticsLoading}
      {showMemberById}
    />
  </aside></div>
  {#snippet footer()}<DuplicateComparisonFooter assetName={selectedData.name} decision={decisions[decisionKey]} {stackLabel} stackPrimary={stackPrimary} decisions={decisionOptions} {disabled} ondecision={setDecision} onprimary={setStackPrimary} onclear={clearDecision}/>{/snippet}
</V2ViewerShell>

<style>
  .v2-thumb-media{position:relative;display:block;width:92px;height:92px;overflow:hidden;border-radius:5px}
  .v2-compare-media-status{display:grid;place-items:center;width:100%;height:100%;padding:var(--v2-space-4);color:var(--v2-muted);background:var(--v2-image-workzone);text-align:center}
  .v2-compare-data{display:grid;grid-template-rows:auto minmax(0,1fr);gap:12px;overflow:hidden}
  .v2-compare-header-zone{min-width:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable both-edges}
  @media(max-width:720px){.v2-compare-data{display:flex;overflow:visible}}
</style>
