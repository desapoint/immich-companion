<script lang="ts">
  import type { DuplicateMemberRecord, SimilarityValidationMode } from '../data/contracts';

  let { member, members, mode, threshold, oninspect }: {
    member: DuplicateMemberRecord;
    members: DuplicateMemberRecord[];
    mode: SimilarityValidationMode | null;
    threshold: number | null;
    oninspect: (assetId: string) => void;
  } = $props();

  const admittedBy = $derived(
    members.find((candidate) => candidate.asset.id === member.admission?.admittedByAssetId),
  );
  const admissionScore = $derived(member.admission?.admissionSimilarityPercent ?? null);
  const belowReference = $derived(
    mode === 'linked'
      && threshold !== null
      && member.similarity !== null
      && member.similarity < threshold
      && admittedBy !== undefined,
  );
</script>

{#if belowReference && admittedBy && admissionScore !== null}
  <small class="v2-admission-note">
    {member.similarity?.toFixed(1)}% vs reference — below {threshold?.toFixed(1)}% threshold.
    Linked through
    <button type="button" onclick={() => oninspect(admittedBy.asset.id)}>
      {admittedBy.asset.original_file_name}
    </button>
    at {admissionScore.toFixed(1)}%.
  </small>
{/if}

<style>
  .v2-admission-note{display:block;padding:7px 9px;border-radius:7px;background:color-mix(in srgb,var(--v2-accent) 9%,transparent);line-height:1.35}
  button{border:0;padding:0;background:transparent;color:var(--v2-accent);font:inherit;font-weight:700;text-decoration:underline;cursor:pointer}
  button:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:3px}
</style>
