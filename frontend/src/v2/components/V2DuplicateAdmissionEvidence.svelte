<script lang="ts">
  import type { DuplicateMemberRecord, SimilarityValidationMode } from '../data/contracts';
  import { formatSimilarityPercent, similarityValidationEvidenceLabel } from '../data/duplicateMember';

  let { member, members, mode, threshold, disabled = false, oninspect }: {
    member: DuplicateMemberRecord;
    members: DuplicateMemberRecord[];
    mode: SimilarityValidationMode | null;
    threshold: number | null;
    disabled?: boolean;
    oninspect: (assetId: string) => void;
  } = $props();

  const admittedBy = $derived(
    members.find((candidate) => candidate.asset.id === member.admission?.admittedByAssetId),
  );
  const admissionScore = $derived(member.admission?.admissionSimilarityPercent ?? null);
  const validationEvidenceLabel = $derived(
    similarityValidationEvidenceLabel(member.similarity, member.similarityEvidence),
  );
  const belowReference = $derived(
    mode === 'linked'
      && threshold !== null
      && member.similarity !== null
      && member.similarity < threshold
      && admittedBy !== undefined,
  );
</script>

{#if validationEvidenceLabel}
  <small class="v2-validation-evidence v2-muted">Validation evidence · <b>{validationEvidenceLabel}</b></small>
{/if}

{#if belowReference && admittedBy && admissionScore !== null}
  <small class="v2-admission-note">
    {formatSimilarityPercent(member.similarity)} vs reference — below {formatSimilarityPercent(threshold)} threshold.
    Linked through
    <button type="button" {disabled} onclick={() => { if (!disabled) oninspect(admittedBy.asset.id); }}>
      {admittedBy.asset.original_file_name}
    </button>
    at {formatSimilarityPercent(admissionScore)}.
  </small>
{/if}

<style>
  .v2-validation-evidence{display:block;line-height:1.35}
  .v2-admission-note{display:block;padding:7px 9px;border-radius:7px;background:color-mix(in srgb,var(--v2-accent) 9%,transparent);line-height:1.35}
  button{border:0;padding:0;background:transparent;color:var(--v2-accent);font:inherit;font-weight:700;text-decoration:underline;cursor:pointer}
  button:disabled{cursor:default;opacity:.55}
  button:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:3px}
</style>
