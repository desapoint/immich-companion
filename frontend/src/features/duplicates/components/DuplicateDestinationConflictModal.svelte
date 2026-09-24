<script lang="ts">
  import { Check, Layers3, Star } from '@lucide/svelte';
  import { assetThumbnailUrl } from '../../../lib/utils/viewerMedia';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import V2LazyAssetMedia from '../../assets/components/LazyAssetMedia.svelte';
  import type {
    DuplicateDestinationConflictResult,
    DuplicateDestinationConflictTarget,
  } from '../state/duplicateDestinationConflictReview';

  let {
    targets,
    choices,
    busy = false,
    onchange,
    onconfirm,
    onclose,
  }: {
    targets: DuplicateDestinationConflictTarget[];
    choices: DuplicateDestinationConflictResult;
    busy?: boolean;
    onchange: (targetId: string, stackId: string) => void;
    onconfirm: () => void;
    onclose: () => void;
  } = $props();

  const allComplete = $derived(targets.every((target) => Boolean(choices[target.id])));

  function sourceCount(target: DuplicateDestinationConflictTarget): number {
    return new Set(target.options.flatMap((stack) => stack.sourceGroupIds?.length ? stack.sourceGroupIds : [stack.groupId])).size;
  }

  function mergedAssetIds(target: DuplicateDestinationConflictTarget): string[] {
    const preferredId = choices[target.id];
    const preferred = target.options.find((stack) => stack.id === preferredId);
    const ordered = preferred
      ? [preferred, ...target.options.filter((stack) => stack.id !== preferred.id)]
      : target.options;
    return [...new Set(ordered.flatMap((stack) => stack.assetIds))];
  }

  function mergedPrimary(target: DuplicateDestinationConflictTarget): string | null {
    return target.options.find((stack) => stack.id === choices[target.id])?.primaryAssetId ?? null;
  }
</script>

<V2ConfirmDialog
  title="Resolve proposed stack overlaps"
  message="Some duplicate groups propose stacks that share the same assets. Choose the preferred destination for each overlap. Companion will merge every connected set of proposed stacks into one final destination before checking existing Immich stacks."
  confirmLabel="Continue to existing stacks"
  icon="stack"
  size="lg"
  pending={busy}
  confirmDisabled={!allComplete}
  {onconfirm}
  {onclose}
>
  <div class="v2-proposed-stack-review">
    {#each targets as target, targetIndex (target.id)}
      {@const previewIds = mergedAssetIds(target)}
      {@const previewPrimary = mergedPrimary(target)}
      <section class="v2-proposed-stack-conflict">
        <header>
          <span>
            <strong>Overlap {targetIndex + 1}</strong>
            <small>{target.options.length} proposed destinations · {target.sharedAssetIds.length} shared asset{target.sharedAssetIds.length === 1 ? '' : 's'} · {sourceCount(target)} duplicate group{sourceCount(target) === 1 ? '' : 's'}</small>
          </span>
          <span class="v2-proposed-stack-merge"><Layers3 size={14} aria-hidden="true"/> Will become one stack</span>
        </header>

        <div class="v2-proposed-stack-options">
          {#each target.options as option (option.id)}
            <button
              type="button"
              class:chosen={choices[target.id] === option.id}
              disabled={busy}
              onclick={() => onchange(target.id, option.id)}
            >
              <span class="v2-proposed-stack-option-heading">
                <span><strong>{option.label}</strong><small>{option.assetIds.length} assets · {(option.sourceGroupIds?.length ?? 1)} source group{(option.sourceGroupIds?.length ?? 1) === 1 ? '' : 's'}</small></span>
                {#if choices[target.id] === option.id}<Check size={15} aria-hidden="true"/>{/if}
              </span>
              <span class="v2-proposed-stack-thumbnails">
                {#each option.assetIds as assetId (assetId)}
                  <span class="v2-proposed-stack-thumb" class:primary={option.primaryAssetId === assetId} class:shared={target.sharedAssetIds.includes(assetId)}>
                    <V2LazyAssetMedia cacheKey={`proposed-stack:${assetId}`} resolve={() => assetThumbnailUrl(assetId, 'thumbnail')} alt="" rootMargin="480px 0px"/>
                    {#if option.primaryAssetId === assetId}<span class="v2-proposed-stack-primary"><Star size={10} fill="currentColor" aria-hidden="true"/></span>{/if}
                    {#if target.sharedAssetIds.includes(assetId)}<span class="v2-proposed-stack-shared">Shared</span>{/if}
                  </span>
                {/each}
              </span>
            </button>
          {/each}
        </div>

        <div class="v2-proposed-stack-preview">
          <span><strong>Merged preview</strong><small>{previewIds.length} assets{previewPrimary ? ' · preferred primary highlighted' : ' · choose a preferred destination'}</small></span>
          <div class="v2-proposed-stack-thumbnails">
            {#each previewIds as assetId (assetId)}
              <span class="v2-proposed-stack-thumb preview" class:primary={previewPrimary === assetId}>
                <V2LazyAssetMedia cacheKey={`proposed-stack-preview:${assetId}`} resolve={() => assetThumbnailUrl(assetId, 'thumbnail')} alt="" rootMargin="480px 0px"/>
                {#if previewPrimary === assetId}<span class="v2-proposed-stack-primary"><Star size={10} fill="currentColor" aria-hidden="true"/></span>{/if}
              </span>
            {/each}
          </div>
        </div>
      </section>
    {/each}
  </div>
</V2ConfirmDialog>

<style>
  .v2-proposed-stack-review{display:grid;gap:12px;min-width:0}
  .v2-proposed-stack-conflict{display:grid;gap:11px;padding:12px;border:1px solid var(--v2-line);border-radius:11px;background:color-mix(in srgb,var(--v2-surface-2) 58%,transparent)}
  .v2-proposed-stack-conflict>header,.v2-proposed-stack-option-heading,.v2-proposed-stack-preview>span{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
  .v2-proposed-stack-conflict header>span:first-child,.v2-proposed-stack-option-heading>span,.v2-proposed-stack-preview>span:first-child{display:grid;gap:2px}
  small{color:var(--v2-muted);line-height:1.35}
  .v2-proposed-stack-merge{display:inline-flex;align-items:center;gap:5px;color:var(--v2-muted);font-size:12px;white-space:nowrap}
  .v2-proposed-stack-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}
  .v2-proposed-stack-options>button{display:grid;gap:8px;min-width:0;padding:10px;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface);color:inherit;text-align:left;cursor:pointer}
  .v2-proposed-stack-options>button:hover:not(:disabled),.v2-proposed-stack-options>button.chosen{border-color:var(--v2-accent);background:color-mix(in srgb,var(--v2-accent) 8%,var(--v2-surface))}
  .v2-proposed-stack-options>button:disabled{cursor:default;opacity:.62}
  .v2-proposed-stack-thumbnails{display:flex;gap:6px;min-width:0;overflow-x:auto;padding:1px 0 3px}
  .v2-proposed-stack-thumb{position:relative;flex:0 0 68px;height:52px;border:1px solid color-mix(in srgb,var(--v2-line) 85%,transparent);border-radius:7px;overflow:hidden;background:#0b1118}
  .v2-proposed-stack-thumb.primary{outline:2px solid color-mix(in srgb,#f8d46e 80%,transparent);outline-offset:-3px}
  .v2-proposed-stack-thumb.shared{border-style:dashed;border-color:var(--v2-accent)}
  .v2-proposed-stack-primary{position:absolute;z-index:2;top:4px;left:4px;width:17px;height:17px;display:grid;place-items:center;border-radius:999px;background:rgba(7,12,18,.9);color:#f8d46e}
  .v2-proposed-stack-shared{position:absolute;z-index:2;right:3px;bottom:3px;padding:2px 4px;border-radius:999px;background:rgba(7,12,18,.88);color:#fff;font-size:8px;font-weight:800}
  .v2-proposed-stack-preview{display:grid;gap:7px;padding:9px;border:1px dashed var(--v2-line);border-radius:9px;background:var(--v2-surface-2)}
  .v2-proposed-stack-thumb.preview{flex-basis:76px;height:58px}
  @media(max-width:720px){.v2-proposed-stack-conflict>header,.v2-proposed-stack-preview>span{align-items:stretch;flex-direction:column}.v2-proposed-stack-merge{white-space:normal}}
</style>
