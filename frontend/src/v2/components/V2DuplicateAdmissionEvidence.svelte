<script lang="ts">
  import { Link2 } from '@lucide/svelte';
  import type { DuplicateMemberRecord, SimilarityValidationMode } from '../data/contracts';
  import { v2AssetViewerPath } from '../navigation';
  import { linkedIntermediateCount } from '../data/duplicateMember';

  let { member, members, mode }: {
    member: DuplicateMemberRecord;
    members: DuplicateMemberRecord[];
    mode: SimilarityValidationMode | null;
  } = $props();

  const admittedBy = $derived(
    members.find((candidate) => candidate.asset.id === member.admission?.admittedByAssetId),
  );
  const linkDepth = $derived(member.admission?.linkDepth ?? null);
  const linkedAdmission = $derived(
    mode === 'linked'
      && linkDepth !== null
      && linkDepth > 0
      && admittedBy !== undefined,
  );
  const intermediateCount = $derived(linkDepth === null ? 0 : linkedIntermediateCount(linkDepth));
  const linkLabel = $derived(
    linkedAdmission && admittedBy
      ? `Linked through ${admittedBy.asset.original_file_name}; ${intermediateCount} ${intermediateCount === 1 ? 'image' : 'images'} in between the group admission reference and this image. Open linked asset in a new tab.`
      : '',
  );
</script>

{#if linkedAdmission && admittedBy && linkDepth !== null}
  <a
    class="v2-linked-admission-pill"
    href={v2AssetViewerPath(admittedBy.asset.id)}
    target="_blank"
    rel="noopener noreferrer"
    title={linkLabel}
    aria-label={linkLabel}
  >
    <span class="v2-linked-admission-icon" aria-hidden="true"><Link2 size={13} strokeWidth={2}/></span>
    <span>{intermediateCount}</span>
  </a>
{/if}

<style>
  .v2-linked-admission-pill{position:absolute;z-index:4;top:8px;left:8px;display:inline-flex;align-items:center;gap:4px;min-height:22px;padding:4px 7px;border:1px solid rgba(255,255,255,.36);border-radius:999px;background:rgba(8,13,19,.86);color:#fff;font-size:10px;font-weight:700;line-height:1;text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.3)}
  .v2-linked-admission-pill:hover{border-color:rgba(255,255,255,.62);background:rgba(8,13,19,.96)}
  .v2-linked-admission-pill:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px}
  .v2-linked-admission-icon{display:inline-flex}
</style>
