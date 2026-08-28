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
    avoidInfoPanel?: boolean;
    onpreview: (assetId: string) => void;
    onrestore: () => void;
    oncommit: (assetId: string) => void;
    onselectviewed: (assetId: string) => void;
  }

  let {
    items,
    source,
    activation,
    selectedId,
    visibleId,
    avoidInfoPanel = false,
    onpreview,
    onrestore,
    oncommit,
    onselectviewed,
  }: Props = $props();
  const interactionLabel = $derived(
    activation === 'hover'
      ? 'Hover to compare'
      : activation === 'press'
        ? 'Hold to compare'
        : 'Click to view',
  );
</script>

<section
  class:avoid-info-panel={avoidInfoPanel}
  class="comparison-tray"
  aria-label={`${source} image comparison`}
>
  <header>
    <div class="tray-heading">
      <span>{source === 'stack' ? 'Stack images' : 'Similar images'}</span>
      <small>{interactionLabel}</small>
    </div>
    <div class="tray-status">
      <button
        type="button"
        class="select-viewed"
        class:hidden={visibleId === selectedId}
        disabled={visibleId === selectedId}
        aria-hidden={visibleId === selectedId}
        onclick={() => { if (visibleId !== selectedId) onselectviewed(visibleId); }}
      >Use viewed as selected</button>
      <strong>{items.length} images</strong>
    </div>
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
    --tray-inline-offset: 0.7rem;
    --tray-max-width: calc(100% - 1.4rem);

    position: absolute;
    z-index: 5;
    bottom: 1.5rem;
    left: var(--tray-inline-offset);
    display: grid;
    width: min(48rem, var(--tray-max-width));
    min-width: 0;
    max-width: var(--tray-max-width);
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
  .tray-heading,
  .tray-status {
    display: flex;
    align-items: center;
  }

  .tray-status {
    flex: none;
    gap: 0.55rem;
  }

  .select-viewed {
    padding: 0.25rem 0.45rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.58rem;
    font-weight: 760;
    white-space: nowrap;
  }

  .select-viewed.hidden {
    visibility: hidden;
  }

  .select-viewed:hover,
  .select-viewed:focus-visible {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  header {
    justify-content: space-between;
    gap: 0.8rem;
    text-align: left;
  }

  .tray-heading {
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
      --tray-inline-offset: 0.25rem;
      --tray-max-width: calc(100% - 0.5rem);

      bottom: 1.25rem;
    }

    .tray-heading {
      align-items: flex-start;
      flex-direction: column;
      gap: 0.1rem;
    }
  }

  @media (min-width: 64rem) {
    .comparison-tray.avoid-info-panel {
      max-width: calc(100% - var(--tray-inline-offset) - 28.25rem);
    }
  }
</style>
