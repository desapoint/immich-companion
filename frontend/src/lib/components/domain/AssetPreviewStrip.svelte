<script lang="ts">
  import type {
    MediaPreviewActivation,
    MediaPreviewItem,
    MediaPreviewSource,
  } from '../../types/media';

  interface Props {
    items: MediaPreviewItem[];
    selectedId: string;
    visibleId: string;
    source?: MediaPreviewSource;
    activation?: MediaPreviewActivation;
    interactive?: boolean;
    compact?: boolean;
    onpreview?: (assetId: string) => void;
    onrestore?: () => void;
    oncommit?: (assetId: string) => void;
  }

  let {
    items,
    selectedId,
    visibleId,
    source = 'stack',
    activation = 'click',
    interactive = true,
    compact = false,
    onpreview,
    onrestore,
    oncommit,
  }: Props = $props();

  let pressedId = $state<string | null>(null);

  function clickItem(event: MouseEvent, assetId: string): void {
    if (!interactive) return;
    if (source === 'similar') {
      oncommit?.(assetId);
    } else if (activation === 'click' || event.detail === 0) {
      onpreview?.(assetId);
    }
  }

  function enterItem(assetId: string): void {
    if (interactive && activation === 'hover') onpreview?.(assetId);
  }

  function leaveItem(): void {
    if (interactive && activation === 'hover') onrestore?.();
  }

  function pressItem(event: PointerEvent, assetId: string): void {
    if (!interactive || activation !== 'press') return;
    const target = event.currentTarget as HTMLElement | null;
    pressedId = assetId;
    target?.setPointerCapture(event.pointerId);
    onpreview?.(assetId);
  }

  function releaseItem(event: PointerEvent): void {
    if (activation !== 'press' || pressedId === null) return;
    const target = event.currentTarget as HTMLElement | null;
    if (target?.hasPointerCapture(event.pointerId)) {
      target.releasePointerCapture(event.pointerId);
    }
    pressedId = null;
    onrestore?.();
  }
</script>

<div
  class:compact
  class:interactive
  class="asset-preview-strip"
  aria-label={source === 'stack' ? 'Stack images' : 'Similar images'}
>
  {#each items as item (item.id)}
    {#if interactive}
      <button
        class:selected={item.id === selectedId}
        class:visible={item.id === visibleId}
        type="button"
        aria-label={`${item.label}${item.id === selectedId ? ', selected' : ''}${item.id === visibleId ? ', currently visible' : ''}`}
        aria-pressed={item.id === selectedId}
        title={item.label}
        onclick={(event) => clickItem(event, item.id)}
        onpointerenter={() => enterItem(item.id)}
        onpointerleave={leaveItem}
        onpointerdown={(event) => pressItem(event, item.id)}
        onpointerup={releaseItem}
        onpointercancel={releaseItem}
      >
        <img src={item.thumbnailUrl} alt="" loading="lazy" decoding="async" draggable="false" />
        <span class="item-state" aria-hidden="true">
          {item.id === selectedId && item.id === visibleId ? 'Selected · Viewing' : item.id === selectedId ? 'Selected' : item.id === visibleId ? 'Viewing' : ''}
        </span>
        {#if item.meta}<small>{item.meta}</small>{/if}
      </button>
    {:else}
      <div class:selected={item.id === selectedId} class:visible={item.id === visibleId} class="preview-item" title={item.label}>
        <img src={item.thumbnailUrl} alt={item.label} loading="lazy" decoding="async" draggable="false" />
        {#if item.meta}<small>{item.meta}</small>{/if}
      </div>
    {/if}
  {/each}
</div>

<style>
  .asset-preview-strip {
    display: flex;
    min-width: 0;
    gap: 0.45rem;
    overflow-x: auto;
    padding: 0.2rem 0.15rem 0.42rem;
    overscroll-behavior-x: contain;
    scrollbar-gutter: stable;
  }

  button,
  .preview-item {
    position: relative;
    display: grid;
    flex: 0 0 6.25rem;
    height: 5.25rem;
    padding: 0;
    overflow: hidden;
    border: 0.16rem solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: white;
    background: #101411;
  }

  button {
    cursor: pointer;
    font: inherit;
  }

  button:hover,
  button:focus-visible {
    border-color: var(--color-accent-hover);
  }

  button.selected {
    border-color: var(--color-accent-strong);
    box-shadow: 0 0 0 0.12rem var(--color-surface-raised), 0 0 0 0.28rem var(--color-accent-strong);
  }

  button.visible {
    outline: 0.16rem solid var(--color-warning-ink);
    outline-offset: -0.34rem;
  }

  button.selected.visible {
    outline-color: var(--color-ink-inverse);
  }

  .preview-item.selected {
    border-color: color-mix(in srgb, var(--color-accent-strong) 55%, var(--color-border-strong));
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    user-select: none;
  }

  .item-state,
  small {
    position: absolute;
    right: 0.18rem;
    left: 0.18rem;
    overflow: hidden;
    padding: 0.18rem 0.28rem;
    border-radius: 0.25rem;
    color: #fff;
    background: rgb(0 0 0 / 74%);
    font-size: 0.48rem;
    font-weight: 800;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-state {
    top: 0.18rem;
  }

  .item-state:empty {
    display: none;
  }

  small {
    bottom: 0.18rem;
    font-weight: 650;
  }

  .compact button,
  .compact .preview-item {
    flex-basis: 4.2rem;
    height: 3.55rem;
  }
</style>
