<script lang="ts">
  import type { AssetSummary } from '../types/assets';

  interface Props {
    asset: AssetSummary;
  }

  let { asset }: Props = $props();
</script>

<div class="state-chips" aria-label="Asset metadata summary">
  {#if asset.is_favorite}<span class="favorite">♥ Favorite</span>{/if}
  {#if asset.is_archived}<span>Archived</span>{/if}
  {#if asset.is_trashed}<span class="warning">Trashed</span>{/if}
  {#if asset.is_offline}<span class="warning">Offline</span>{/if}
  {#if asset.is_edited}<span>Edited</span>{/if}
  {#if asset.live_photo_video_id}<span>Live photo</span>{/if}
  {#if asset.people_count}<span>{asset.people_count} people</span>{/if}
  {#if asset.tag_count}<span>{asset.tag_count} tags</span>{/if}
  {#if asset.stack_count}<span>{asset.stack_count} stacked</span>{/if}
</div>

<style>
  .state-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    min-height: 1.45rem;
  }

  span {
    padding: 0.24rem 0.48rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.65rem;
    font-weight: 720;
  }

  .favorite {
    color: var(--color-positive-ink);
    border-color: var(--color-positive-border);
    background: var(--color-positive-surface);
  }

  .warning {
    color: var(--color-warning-ink);
    border-color: var(--color-warning-border);
    background: var(--color-warning-surface);
  }
</style>
