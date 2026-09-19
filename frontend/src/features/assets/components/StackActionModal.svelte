<script lang="ts">
  import { Check, Star } from '@lucide/svelte';
  import { assetThumbnailUrl } from '../../../lib/utils/viewerMedia';
  import type { StackActionPlan, StackConflict, StackResolution, StackResolutionMap, StackResolutionSelection } from '../../../lib/types/libraryContracts';
  import {
    conflictResolutionMap,
    projectedStackCount,
    serializeStackResolution,
    sharedConflictIds,
    stackReviewComplete,
    withConflictResolution,
    type StackConflictReviewTarget,
  } from '../../../features/duplicates/types/stackResolution';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import V2LazyAssetMedia from './LazyAssetMedia.svelte';

  let {
    reviews,
    plan = null,
    primaryLabel = '',
    resolution = null,
    busy = false,
    onresolutionchange,
    onreviewresolutionchange,
    onconfirm,
    onclose,
  }: {
    reviews?: StackConflictReviewTarget[];
    plan?: StackActionPlan | null;
    primaryLabel?: string;
    resolution?: StackResolutionSelection | null;
    busy?: boolean;
    onresolutionchange?: (resolution: StackResolution) => void;
    onreviewresolutionchange?: (reviewId: string, resolution: StackResolutionMap) => void;
    onconfirm: () => void;
    onclose: () => void;
  } = $props();

  const options: Array<{ value: StackResolution; label: string; description: string }> = [
    { value: 'move_selected', label: 'Move selected assets', description: 'Move only highlighted members into the new stack. The old stack keeps unselected members when possible.' },
    { value: 'keep_existing', label: 'Keep existing stacks', description: 'Leave this existing stack untouched and exclude its selected members from the new stack.' },
    { value: 'include_existing', label: 'Include every member', description: 'Bring every member of this existing stack into the new stack.' },
  ];

  const activeReviews = $derived<StackConflictReviewTarget[]>(reviews ?? (plan ? [{ id: 'asset-stack-review', label: 'New stack', primaryLabel, plan, resolution }] : []));
  const conflictCount = $derived(activeReviews.reduce((count, review) => count + review.plan.conflicts.length, 0));
  const sharedIds = $derived(sharedConflictIds(activeReviews));
  const allComplete = $derived(conflictCount === 0 || activeReviews.every((review) => stackReviewComplete(review) && !hasSharedMutation(review)));
  const dialogMessage = $derived(conflictCount === 0 && plan
    ? `${plan.targetCount.toLocaleString()} selected assets will be placed in one stack.`
    : conflictCount === 1
      ? 'One existing stack overlaps the stack you are creating. Review how it should be reconciled.'
      : `${conflictCount.toLocaleString()} existing stack conflicts overlap the stacks you are creating. Resolve each one before continuing.`);

  function choices(review: StackConflictReviewTarget): StackResolutionMap {
    return conflictResolutionMap(review.plan, review.resolution);
  }

  function selectedChoice(review: StackConflictReviewTarget, stackId: string): StackResolution | '' {
    return choices(review)[stackId] ?? '';
  }

  function selectedIds(conflict: StackConflict): string[] {
    return conflict.selectedAssetIds ?? [];
  }

  function memberIds(conflict: StackConflict): string[] {
    return conflict.memberAssetIds ?? [];
  }

  function optionAllowed(review: StackConflictReviewTarget, conflict: StackConflict, choice: StackResolution): boolean {
    if (sharedIds.has(conflict.stackId) && choice !== 'keep_existing') return false;
    if (choice === 'keep_existing' && selectedIds(conflict).includes(review.plan.primaryAssetId)) return false;
    if (choice === 'include_existing' && !conflict.includesUnselected) return false;
    return true;
  }

  function hasSharedMutation(review: StackConflictReviewTarget): boolean {
    const current = choices(review);
    return review.plan.conflicts.some((conflict) => sharedIds.has(conflict.stackId) && current[conflict.stackId] && current[conflict.stackId] !== 'keep_existing');
  }

  function emitResolution(reviewId: string, next: StackResolutionMap): void {
    if (reviews !== undefined) {
      onreviewresolutionchange?.(reviewId, next);
      return;
    }
    // V2AssetsPage still stores the reviewed value in its legacy scalar state. The
    // repository parser accepts the canonical serialized map and restores it here.
    onresolutionchange?.(serializeStackResolution(next) as StackResolution);
  }

  function change(review: StackConflictReviewTarget, conflict: StackConflict, value: string): void {
    if (!value) return;
    const choice = value as StackResolution;
    if (!optionAllowed(review, conflict, choice)) return;
    emitResolution(review.id, withConflictResolution(review.plan, review.resolution, conflict.stackId, choice));
  }

  function applyAll(choice: StackResolution): void {
    for (const review of activeReviews) {
      let next = choices(review);
      let changed = false;
      for (const conflict of review.plan.conflicts) {
        if (!optionAllowed(review, conflict, choice)) continue;
        next = { ...next, [conflict.stackId]: choice };
        changed = true;
      }
      if (changed) emitResolution(review.id, next);
    }
  }

  function resolutionWarning(review: StackConflictReviewTarget): string | null {
    const projected = projectedStackCount(review.plan, review.resolution);
    if (projected < 2) return 'This combination leaves fewer than two assets for the new stack.';
    const current = choices(review);
    const primaryConflict = review.plan.conflicts.find((conflict) => selectedIds(conflict).includes(review.plan.primaryAssetId));
    if (primaryConflict && current[primaryConflict.stackId] === 'keep_existing') return 'The chosen new-stack primary would remain in its existing stack. Choose another resolution.';
    if (hasSharedMutation(review)) return 'This existing stack is also used by another destination. Keep it existing in both destinations, or resolve the destinations separately.';
    return null;
  }
</script>

<V2ConfirmDialog
  title="Resolve existing stacks"
  message={dialogMessage}
  confirmLabel="Continue"
  icon="stack"
  size="lg"
  pending={busy}
  confirmDisabled={!allComplete}
  {onconfirm}
  {onclose}
>
  {#if conflictCount > 0}
    <div class="v2-stack-review">
      {#if conflictCount > 1}
        <div class="v2-stack-bulk">
          <span><strong>Apply where compatible</strong><small>You can set a common choice first, then adjust individual stacks.</small></span>
          <div class="v2-stack-bulk-actions">
            {#each options as option (option.value)}
              <V2Button disabled={busy} onclick={() => applyAll(option.value)}>{option.label}</V2Button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="v2-stack-review-list">
        {#each activeReviews as review (review.id)}
          {@const warning = resolutionWarning(review)}
          <section class="v2-stack-destination">
            <header>
              <span><strong>{review.label}</strong><small>{review.plan.targetCount.toLocaleString()} selected · projected {projectedStackCount(review.plan, review.resolution).toLocaleString()} in new stack</small></span>
              <span class="v2-stack-primary"><Star size={13} fill="currentColor" aria-hidden="true"/> New primary: {review.primaryLabel}</span>
            </header>

            {#each review.plan.conflicts as conflict, index (conflict.stackId)}
              {@const members = memberIds(conflict)}
              {@const selected = selectedIds(conflict)}
              <article class="v2-stack-conflict" data-shared={sharedIds.has(conflict.stackId) || undefined}>
                <div class="v2-stack-conflict-heading">
                  <span><strong>Existing stack {index + 1}</strong><small>{conflict.memberCount} assets · {conflict.selectedCount} selected{sharedIds.has(conflict.stackId) ? ' · also overlaps another new stack' : ''}</small></span>
                  <label>
                    <span class="sr-only">Resolution for existing stack {index + 1}</span>
                    <select disabled={busy} value={selectedChoice(review, conflict.stackId)} onchange={(event) => change(review, conflict, event.currentTarget.value)}>
                      <option value="" disabled>Choose action…</option>
                      {#each options as option (option.value)}
                        {#if optionAllowed(review, conflict, option.value)}
                          <option value={option.value}>{option.label}</option>
                        {/if}
                      {/each}
                    </select>
                  </label>
                </div>

                {#if members.length}
                  <div class="v2-stack-thumbnails" aria-label={`Members of existing stack ${index + 1}`}>
                    {#each members as assetId (assetId)}
                      <div
                        class="v2-stack-thumb"
                        class:selected={selected.includes(assetId)}
                        class:primary={conflict.primaryAssetId === assetId}
                        title={`${selected.includes(assetId) ? 'Selected for new stack' : 'Existing stack member'}${conflict.primaryAssetId === assetId ? ' · current primary' : ''}`}
                      >
                        <V2LazyAssetMedia cacheKey={`stack-conflict:${assetId}`} resolve={() => assetThumbnailUrl(assetId, 'thumbnail')} alt="" rootMargin="480px 0px"/>
                        {#if conflict.primaryAssetId === assetId}<span class="v2-stack-thumb-primary"><Star size={10} fill="currentColor" aria-hidden="true"/></span>{/if}
                        {#if selected.includes(assetId)}<span class="v2-stack-thumb-selected"><Check size={10} aria-hidden="true"/> Selected</span>{/if}
                      </div>
                    {/each}
                  </div>
                {:else}
                  <span class="v2-stack-visual-unavailable">Stack thumbnails are unavailable for this legacy preview.</span>
                {/if}

                {#if selectedChoice(review, conflict.stackId)}
                  {@const description = options.find((option) => option.value === selectedChoice(review, conflict.stackId))?.description}
                  {#if description}<p class="v2-stack-description">{description}</p>{/if}
                {/if}
              </article>
            {/each}
            {#if warning}<p class="v2-stack-warning">{warning}</p>{/if}
          </section>
        {/each}
      </div>
    </div>
  {/if}
</V2ConfirmDialog>

<style>
  .v2-stack-review{display:grid;gap:12px;min-width:0}
  .v2-stack-review-list{display:grid;gap:12px;max-height:min(62vh,680px);overflow:auto;padding-right:4px}
  .v2-stack-bulk{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px;border:1px solid var(--v2-line);border-radius:10px;background:var(--v2-surface-2)}
  .v2-stack-bulk>span,.v2-stack-destination header>span,.v2-stack-conflict-heading>span{display:grid;gap:2px;min-width:0}
  .v2-stack-bulk small,.v2-stack-destination small,.v2-stack-conflict-heading small{color:var(--v2-muted);line-height:1.35}
  .v2-stack-bulk-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
  .v2-stack-destination{display:grid;gap:9px;padding:11px;border:1px solid var(--v2-line);border-radius:11px;background:color-mix(in srgb,var(--v2-surface-2) 58%,transparent)}
  .v2-stack-destination header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
  .v2-stack-primary{display:inline-flex!important;grid-auto-flow:column;align-items:center;gap:5px!important;white-space:nowrap;color:var(--v2-muted);font-size:12px}
  .v2-stack-conflict{display:grid;gap:8px;padding:9px;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface)}
  .v2-stack-conflict[data-shared='true']{border-style:dashed}
  .v2-stack-conflict-heading{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .v2-stack-conflict-heading select{min-width:150px;max-width:210px;border:1px solid var(--v2-line);border-radius:7px;background:var(--v2-surface-2);color:var(--v2-text);padding:7px 9px;font:inherit}
  .v2-stack-thumbnails{display:flex;gap:7px;min-width:0;overflow-x:auto;padding:2px 1px 5px}
  .v2-stack-thumb{position:relative;flex:0 0 78px;height:58px;border:1px solid color-mix(in srgb,var(--v2-line) 85%,transparent);border-radius:8px;overflow:hidden;background:#0b1118;box-shadow:none}
  .v2-stack-thumb.selected{border-color:var(--v2-accent);box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--v2-accent) 72%,transparent)}
  .v2-stack-thumb.primary{outline:1px solid color-mix(in srgb,#f8d46e 75%,transparent);outline-offset:-3px}
  .v2-stack-thumb-primary{position:absolute;z-index:2;top:4px;left:4px;width:18px;height:18px;display:grid;place-items:center;border-radius:999px;background:rgba(7,12,18,.9);color:#f8d46e}
  .v2-stack-thumb-selected{position:absolute;z-index:2;right:4px;bottom:4px;display:flex;align-items:center;gap:3px;padding:3px 5px;border-radius:999px;background:rgba(7,12,18,.88);color:#fff;font-size:9px;font-weight:700}
  .v2-stack-warning{margin:0;padding:7px 8px;border-radius:7px;background:color-mix(in srgb,var(--v2-red) 12%,transparent);color:var(--v2-red);font-size:12px;line-height:1.35}
  .v2-stack-description,.v2-stack-visual-unavailable{margin:0;color:var(--v2-muted);font-size:12px;line-height:1.35}
  .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
  @media(max-width:720px){.v2-stack-bulk,.v2-stack-destination header,.v2-stack-conflict-heading{align-items:stretch;flex-direction:column}.v2-stack-primary{white-space:normal}.v2-stack-conflict-heading select{width:100%;max-width:none}.v2-stack-bulk-actions{justify-content:flex-start}}
</style>
