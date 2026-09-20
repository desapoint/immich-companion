<script lang="ts">
  import type { ComparisonMemberData } from '../types/duplicateMember';
  import type { DuplicateAdmissionEvidence, DuplicateMemberRecord, DuplicateSimilarityEvidence } from '../types/contracts';
  import type { LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
  import { formatSimilarityPercent } from '../types/duplicateMember';

  type MetadataRow = { label: string; selected: string; reference: string; changed: boolean };

  let {
    selectedData,
    referenceData,
    assetIds,
    metadataRows,
    hasIndirectLinkedAdmission,
    selectedAdmission,
    admittedByMember,
    admittedByLabel,
    bestGroupMatchLabel,
    intermediateImageCount,
    modeLabel,
    thresholdLabel,
    selectedSimilarity,
    belowThreshold,
    selectedEvidence,
    validationEvidenceLabel,
    boundedValidation,
    selectedValidatedDimensions,
    referenceValidatedDimensions,
    sizeDifferenceLabel,
    sameResolution,
    sameSourceCollection,
    folderScopeLabel,
    foldersComparable,
    sameFolder,
    localDiagnostics,
    localDiagnosticsLoading,
    showMemberById,
  }: {
    selectedData: ComparisonMemberData;
    referenceData: ComparisonMemberData;
    assetIds: string[];
    metadataRows: MetadataRow[];
    hasIndirectLinkedAdmission: boolean;
    selectedAdmission: DuplicateAdmissionEvidence | null;
    admittedByMember: DuplicateMemberRecord | null | undefined;
    admittedByLabel: string;
    bestGroupMatchLabel: string;
    intermediateImageCount: number;
    modeLabel: string;
    thresholdLabel: string;
    selectedSimilarity: number | null;
    belowThreshold: boolean;
    selectedEvidence: DuplicateSimilarityEvidence | null;
    validationEvidenceLabel: string | null;
    boundedValidation: boolean;
    selectedValidatedDimensions: string | null;
    referenceValidatedDimensions: string | null;
    sizeDifferenceLabel: string;
    sameResolution: boolean;
    sameSourceCollection: boolean;
    folderScopeLabel: string;
    foldersComparable: boolean;
    sameFolder: boolean;
    localDiagnostics: LocalChangeDiagnostics | null;
    localDiagnosticsLoading: boolean;
    showMemberById: (assetId: string) => void;
  } = $props();

  function percent(value: number | null | undefined): string {
    return formatSimilarityPercent(value ?? null);
  }

  function detailSourceLabel(value: DuplicateSimilarityEvidence['detailSource']): string {
    if (value === 'original') return 'Original';
    if (value === 'transcoded') return 'Full-size conversion';
    if (value === 'preview') return 'Bounded preview';
    return 'Unavailable';
  }
</script>

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
          <span>Admitted through</span>
          {#if admittedByMember && assetIds.includes(admittedByMember.asset.id)}
            <button type="button" class="v2-compare-link-value v2-compare-member-link" title={`Select ${admittedByLabel} in the comparison viewer`} aria-label={`Select admitted-through asset ${admittedByLabel} in the comparison viewer`} onclick={() => showMemberById(admittedByMember.asset.id)}>{admittedByLabel}</button>
          {:else}
            <b class="v2-compare-link-value">{admittedByLabel}</b>
          {/if}
          <span>Admission similarity</span><b>{formatSimilarityPercent(selectedAdmission.admissionSimilarityPercent)}</b>
          <span>Images in between</span><b>{intermediateImageCount}</b>
          <span>Best group match</span><b class="v2-compare-link-value">{bestGroupMatchLabel}</b>
          <span>Best group similarity</span><b>{formatSimilarityPercent(selectedAdmission.bestGroupMatchSimilarityPercent)}</b>
        </div>
        <p class="v2-compare-detail-note">“Images in between” counts only intermediate members between the group admission reference and this image; it does not count either endpoint. Changing the comparison reference does not rewrite the stored admission chain. “Admitted through” is the comparison edge that allowed this member into a linked group. “Best group match” is the strongest known relationship in the group and can be a different image.</p>
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
          <span>Frame alignment</span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? (localDiagnostics.alignmentApplied ? 'Applied' : 'Not needed') : 'Unavailable'}</b>
          {#if !localDiagnosticsLoading && localDiagnostics?.available}
            {#if localDiagnostics.alignmentApplied}
              <span>Unaligned detail score</span><b>{percent(localDiagnostics.rawSimilarityPercent)}</b>
              <span>Aligned detail score</span><b>{percent(localDiagnostics.alignedSimilarityPercent)}</b>
            {:else}
              <span>Detail score</span><b>{percent(localDiagnostics.alignedSimilarityPercent)}</b>
            {/if}
          {/if}
          {#if selectedEvidence.detailChangedPercent !== null && selectedEvidence.detailChangedPercent !== undefined}
            <span>Aligned detail changed area <small class="v2-muted">· scorer</small></span><b>{percent(selectedEvidence.detailChangedPercent)}</b>
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
      {#if boundedValidation}<p class="v2-compare-detail-note">At least one side cannot be fully decoded within Companion's 64-megapixel safety limit, or its original/full-size detail evidence was unavailable. Similarity therefore uses bounded Immich-generated visual evidence. The metadata table shows original dimensions and the actual rendition dimensions used when they are known. Bounded validation is review evidence, not full-resolution or destructive proof.</p>{/if}
      {#if selectedEvidence?.detailChangedPercent !== null && selectedEvidence?.detailChangedPercent !== undefined}<p class="v2-compare-detail-note">The final similarity uses the aligned detail result when alignment is applied; the unaligned detail score is shown only to explain the effect of compensation. The original images are never warped in the viewer. Difference shows displayed-pixel changes; Local changes deliberately keeps the raw original-coordinate grid.</p>{/if}
    </div>
  </details>

  <details class="v2-compare-detail">
    <summary>Local-change validator</summary>
    <div class="v2-compare-detail-body">
      <div class="v2-compare-key-values">
        <span>Raw changed area <small class="v2-muted">· viewer grid</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.changedPercent) : 'Unavailable'}</b>
        <span>Aligned changed area <small class="v2-muted">· scorer</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.alignedChangedPercent) : 'Unavailable'}</b>
        <span>Frame-shift compensation</span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? (localDiagnostics.alignmentApplied ? `Applied · ${percent(localDiagnostics.alignmentShiftPercent)} shift` : 'Not needed') : 'Unavailable'}</b>
        <span>Aligned overlap</span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.alignmentOverlapPercent) : 'Unavailable'}</b>
        <span>Peak local change <small class="v2-muted">· raw grid</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.localizedChangedPercent) : 'Unavailable'}</b>
        <span>Coherent changed area <small class="v2-muted">· raw grid</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.coherentChangedPercent) : 'Unavailable'}</b>
        <span>Largest changed region <small class="v2-muted">· raw grid</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? percent(localDiagnostics.largestChangedRegionPercent) : 'Unavailable'}</b>
        <span>Substantial regions <small class="v2-muted">· raw grid</small></span><b>{localDiagnosticsLoading ? 'Calculating…' : localDiagnostics?.available ? (localDiagnostics.substantialRegionCount ?? '—') : 'Unavailable'}</b>
      </div>
      <p class="v2-compare-detail-note">The Local changes overlay stays in the originals' raw coordinate space so its cells line up with the image you see. Similarity scoring separately uses aligned residuals: matching coverage is the primary signal, while difference magnitude and multiple spatially separated changed zones apply bounded penalties. One localized coherent change is not independently punished just for being coherent.</p>
    </div>
  </details>

  <details class="v2-compare-detail">
    <summary>File differences</summary>
    <div class="v2-compare-detail-body"><div class="v2-compare-key-values">
      <span>File size difference</span><b>{sizeDifferenceLabel}</b>
      <span>Resolution</span><b>{sameResolution ? 'Same' : 'Different'}</b>
      {#if sameSourceCollection}<span>{folderScopeLabel}</span><b>{!foldersComparable ? 'Unavailable' : sameFolder ? 'Same' : 'Different'}</b>{/if}
      <span>Difference source</span><b>Layered displayed pixels</b>
    </div></div>
  </details>

  {#if hasIndirectLinkedAdmission && selectedAdmission}
    <details class="v2-compare-detail"><summary>Technical linked data</summary><div class="v2-compare-detail-body"><div class="v2-compare-key-values">
      <span>Model version</span><b class="v2-compare-technical-value">{selectedAdmission.modelVersion}</b>
      <span>Feature version</span><b>{selectedAdmission.featureVersion}</b>
      <span>Comparison version</span><b>{selectedAdmission.comparisonVersion}</b>
      <span>Config fingerprint</span><b class="v2-compare-technical-value">{selectedAdmission.configFingerprint}</b>
    </div></div></details>
  {/if}
</div>

<style>
  .v2-compare-detail-scroll{display:flex;flex-direction:column;align-items:stretch;gap:12px;min-width:0;min-height:0;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable both-edges}
  .v2-compare-detail-scroll>.v2-compare-detail{flex:0 0 auto}
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
  .v2-compare-member-link{min-width:0;max-width:13rem;margin:0;padding:0;border:0;background:transparent;font:inherit;font-weight:700;text-align:right;text-decoration:underline;overflow-wrap:anywhere;cursor:pointer}
  .v2-compare-member-link:hover{color:color-mix(in srgb,var(--v2-accent) 75%,white)!important}
  .v2-compare-member-link:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:3px}
  .v2-compare-detail-note{margin:10px 0 0;padding:8px 9px;border-left:3px solid color-mix(in srgb,var(--v2-accent) 45%,var(--v2-line));background:color-mix(in srgb,var(--v2-accent) 6%,transparent);color:var(--v2-muted);font-size:11px;line-height:1.45}
  .v2-compare-metadata-body{overflow:hidden}
  .v2-compare-metadata-body :global(.v2-compare-grid){width:100%;max-width:100%;overflow:hidden}
  .v2-compare-technical-value{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10px;word-break:break-all}
  .warn-value{color:#e3c66f}
  @media(max-width:720px){.v2-compare-detail-scroll{overflow:visible;scrollbar-gutter:auto}.v2-compare-key-values{grid-template-columns:1fr}.v2-compare-key-values>b{text-align:left;max-width:none}.v2-compare-member-link{text-align:left;max-width:none}}
</style>
