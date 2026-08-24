<script lang="ts">
  import AssetPreviewStrip from '../../../lib/components/domain/AssetPreviewStrip.svelte';
  import type { MediaPreviewItem } from '../../../lib/types/media';
  import type {
    AssetComparisonActivation,
    AssetComparisonSource,
  } from '../types/assets';

  interface Props {
    items: MediaPreviewItem[];
    source: AssetComparisonSource;
    activation: AssetComparisonActivation;
    selectedId: string;
    visibleId: string;
    onpreview: (assetId: string) => void;
    onrestore: () => void;
    oncommit: (assetId: string) => void;
  }

  let {
    items,
    source,
    activation,
    selectedId,
    visibleId,
    onpreview,
    onrestore,
    oncommit,
  }: Props = $props();
  const interactionLabel = $derived(
    activation === 'hover'
      ? 'Hover to compare'
      : activation === 'press'
        ? 'Hold to compare'
        : 'Click to view',
  );
</script>

<section class="comparison-tray" aria-label={`${source} image comparison`}>
  <header>
    <div>
      <span>{source === 'stack' ? 'Stack images' : 'Similar images'}</span>
      <small>{interactionLabel}</small>
    </div>
    <strong>{items.length} images</strong>
  </header>
  <AssetPreviewStrip
    {items}
    {selectedId}
    {visibleId}
    {source}
    {activation}
    {onpreview}
    {onrestore}
    {oncommit}
  />
</section>

<style>
  .comparison-tray {
    position: absolute;
    z-index: 5;
    right: clamp(3.5rem, 7vw, 6rem);
    bottom: 0.75rem;
    left: clamp(3.5rem, 7vw, 6rem);
    display: grid;
    min-width: 0;
    max-height: calc(100% - 1.5rem);
    gap: 0.3rem;
    padding: 0.55rem 0.7rem 0.3rem;
    overflow: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: color-mix(in srgb, var(--color-surface-raised) 94%, transparent);
    box-shadow: 0 0.85rem 2.6rem rgb(0 0 0 / 34%);
    backdrop-filter: blur(0.65rem);
  }

  header,
  header > div {
    display: flex;
    align-items: center;
  }

  header {
    justify-content: space-between;
    gap: 0.8rem;
  }

  header > div {
    gap: 0.48rem;
  }

  header span {
    color: var(--color-accent-strong);
    font-size: 0.66rem;
    font-weight: 820;
    text-transform: uppercase;
  }

  header small,
  header strong {
    color: var(--color-ink-muted);
    font-size: 0.58rem;
  }

  @media (max-width: 38rem) {
    .comparison-tray {
      right: 2.8rem;
      bottom: 0.45rem;
      left: 2.8rem;
    }

    header > div {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.1rem;
    }
  }
</style>
