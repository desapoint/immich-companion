<script lang="ts">
  import { safeAssetTagColor } from '../state/assetTagViewModel';
  import type { AssetTagSummary } from '../types/assets';

  interface Props {
    tags: AssetTagSummary[];
    maxVisible?: number;
  }

  let { tags, maxVisible = 3 }: Props = $props();
  const visibleTags = $derived(tags.slice(0, Math.max(1, maxVisible)));
  const hiddenCount = $derived(Math.max(0, tags.length - visibleTags.length));
</script>

{#if tags.length}
  <div class="asset-tags" aria-label="Image tags">
    {#each visibleTags as tag (tag.id)}
      <span class="asset-tag" title={tag.name}>
        <i style:background={safeAssetTagColor(tag.color)} aria-hidden="true"></i>
        <span>{tag.name}</span>
      </span>
    {/each}
    {#if hiddenCount}<span class="more-tags" title={`${hiddenCount} more tags`}>+{hiddenCount}</span>{/if}
  </div>
{/if}

<style>
  .asset-tags {
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    gap: 0.32rem;
  }

  .asset-tag,
  .more-tags {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 0.32rem;
    padding: 0.24rem 0.42rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.62rem;
    font-weight: 720;
  }

  .asset-tag {
    max-width: 100%;
  }

  .asset-tag i {
    flex: 0 0 auto;
    width: 0.48rem;
    height: 0.48rem;
    border: 1px solid rgb(0 0 0 / 18%);
    border-radius: 50%;
  }

  .asset-tag span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .more-tags {
    flex: 0 0 auto;
    color: var(--color-accent-strong);
  }
</style>
