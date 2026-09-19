<script lang="ts">
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import { formatSimilarityPercent, type ComparisonMemberData } from '../types/duplicateMember';
  import type { DuplicateSimilarityEvidence } from '../types/contracts';

  let {
    matchLabel,
    modeLabel,
    groupSimilarityTitle,
    groupSimilarityLabel,
    selectedData,
    selectedEvidence,
    selectedSimilarity,
    validationEvidenceLabel,
    boundedValidation,
    showLinkedSummary,
    admittedByLabel,
    selectedAdmission,
    belowThreshold,
    thresholdLabel,
    validationMode,
    sizeDifferenceLabel,
    sameResolution,
    sameSourceCollection,
    foldersComparable,
    sameFolder,
  }: {
    matchLabel: string;
    modeLabel: string;
    groupSimilarityTitle: string;
    groupSimilarityLabel: string;
    selectedData: ComparisonMemberData;
    selectedEvidence: DuplicateSimilarityEvidence | null;
    selectedSimilarity: number | null;
    validationEvidenceLabel: string | null;
    boundedValidation: boolean;
    showLinkedSummary: boolean;
    admittedByLabel: string;
    selectedAdmission: { admissionSimilarityPercent: number | null } | null;
    belowThreshold: boolean;
    thresholdLabel: string;
    validationMode: string | null;
    sizeDifferenceLabel: string;
    sameResolution: boolean;
    sameSourceCollection: boolean;
    foldersComparable: boolean;
    sameFolder: boolean;
  } = $props();

  function percent(value: number | null): string {
    return formatSimilarityPercent(value);
  }
</script>

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
      {#if selectedSimilarity !== null && thresholdLabel !== 'Unavailable'}
        <span class="v2-compare-chip" class:warn={belowThreshold} class:ok={!belowThreshold}>{belowThreshold ? 'Below' : 'Above'} {thresholdLabel} threshold</span>
      {:else if validationMode === 'linked' && selectedSimilarity === null}
        <span class="v2-compare-chip warn">Reference score unavailable</span>
      {/if}
      <span class="v2-compare-chip">{sizeDifferenceLabel}</span>
      <span class="v2-compare-chip" class:warn={!sameResolution} class:ok={sameResolution}>{sameResolution ? 'Same' : 'Different'} resolution</span>
      {#if sameSourceCollection}<span class="v2-compare-chip" class:warn={!foldersComparable || !sameFolder} class:ok={foldersComparable && sameFolder}>{!foldersComparable ? 'Folder unavailable' : sameFolder ? 'Same folder' : 'Different folder'}</span>{/if}
    </div>
  </div>
</V2Card>

<style>
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
</style>
