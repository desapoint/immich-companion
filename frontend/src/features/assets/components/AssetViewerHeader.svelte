<script lang="ts">
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetSelectionSummary,
    TagOption,
    ViewerScaleMode,
  } from '../types/assets';
  import AssetActionControls from './AssetActionControls.svelte';
  import AssetKeyboardHelp from './AssetKeyboardHelp.svelte';

  interface Props {
    filename: string;
    selectedFilename: string;
    selected: boolean;
    scaleMode: ViewerScaleMode;
    infoOpen: boolean;
    helpOpen: boolean;
    zoomPercent: number;
    actionSummary: AssetSelectionSummary | null;
    albums: AlbumOption[];
    tags: TagOption[];
    hasStack?: boolean;
    isVisibleStackPrimary?: boolean;
    actionBusy?: boolean;
    actionError?: string | null;
    onaction: (action: AssetActionIntent, relationIds?: string[]) => void;
    onsetprimary?: () => void;
    onrelationconfirm: (
      action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
      relationIds: string[],
    ) => void;
    ontoggleselection: () => void;
    ontogglescale: () => void;
    onzoomout: () => void;
    onzoomreset: () => void;
    onzoomin: () => void;
    ontoggleinfo: () => void;
    ontogglehelp: () => void;
    onclose: () => void;
  }

  let {
    filename,
    selectedFilename,
    selected,
    scaleMode,
    infoOpen,
    helpOpen,
    zoomPercent,
    actionSummary,
    albums,
    tags,
    hasStack = false,
    isVisibleStackPrimary = false,
    actionBusy = false,
    actionError = null,
    onaction,
    onsetprimary,
    onrelationconfirm,
    ontoggleselection,
    ontogglescale,
    onzoomout,
    onzoomreset,
    onzoomin,
    ontoggleinfo,
    ontogglehelp,
    onclose,
  }: Props = $props();
</script>

<header class="viewer-header">
  <div class="viewer-identity">
    <span>{filename === selectedFilename ? 'Asset viewer' : `Stack preview · selected ${selectedFilename}`}</span>
    <h2 id="asset-viewer-title" title={filename}>{filename}</h2>
    {#if actionError}<small class="action-error" role="alert">{actionError}</small>{/if}
  </div>

  <div class="viewer-actions">
    <AssetActionControls
      summary={actionSummary}
      {albums}
      {tags}
      targetCount={1}
      targetLabel="selected image"
      allowStack={false}
      allowStackRemoval={hasStack}
      isStackPrimary={isVisibleStackPrimary}
      {onsetprimary}
      busy={actionBusy}
      onplan={onaction}
      {onrelationconfirm}
    />
    <span class="viewer-action-separator" aria-hidden="true"></span>
    <IconButton
      icon={selected ? 'check' : 'select'}
      label={selected ? 'Deselect image' : 'Select image'}
      tone={selected ? 'accent' : 'default'}
      onclick={ontoggleselection}
    />
    <IconButton
      icon={scaleMode === 'fit' ? 'actual-size' : 'fit'}
      label={scaleMode === 'fit' ? 'Show actual size' : 'Fit image to screen'}
      onclick={ontogglescale}
    />
    <div class="zoom-actions" role="group" aria-label="Image zoom controls">
      <IconButton icon="zoom-out" label="Zoom out (-)" onclick={onzoomout} />
      <button
        class="zoom-reset"
        type="button"
        onclick={onzoomreset}
        aria-label={`Reset zoom to fit (${zoomPercent}% currently)`}
        title="Reset zoom to fit (0)"
      >{zoomPercent}%</button>
      <IconButton icon="zoom-in" label="Zoom in (+)" onclick={onzoomin} />
    </div>
    <IconButton
      icon="info"
      label={infoOpen ? 'Hide more info' : 'Show more info'}
      tone={infoOpen ? 'accent' : 'default'}
      onclick={ontoggleinfo}
    />
    <div class="help-action">
      <IconButton
        icon="keyboard"
        label={helpOpen ? 'Hide keyboard shortcuts' : 'Show keyboard shortcuts'}
        tone={helpOpen ? 'accent' : 'default'}
        onclick={ontogglehelp}
      />
      {#if helpOpen}<AssetKeyboardHelp />{/if}
    </div>
    <IconButton icon="close" label="Close asset viewer" onclick={onclose} />
  </div>
</header>

<style>
  .viewer-header {
    position: relative;
    z-index: 5;
    display: flex;
    flex: none;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    min-width: 0;
    padding: 0.7rem 0.85rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: var(--color-surface-raised);
  }

  .viewer-identity {
    display: grid;
    min-width: 0;
    gap: 0.14rem;
  }

  .viewer-identity span {
    color: var(--color-accent-strong);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  .viewer-identity .action-error {
    color: var(--color-negative-ink);
    font-size: 0.64rem;
  }

  h2 {
    max-width: min(34vw, 32rem);
    margin: 0;
    overflow: hidden;
    font-size: 0.88rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .viewer-actions {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 0.38rem;
  }

  .viewer-action-separator {
    width: 1px;
    height: 2.2rem;
    background: var(--color-border-strong);
  }

  button {
    min-height: 2.3rem;
    padding: 0.48rem 0.7rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-soft);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 760;
  }

  button:hover {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  .help-action {
    position: relative;
  }

  .zoom-actions {
    display: flex;
    align-items: center;
    overflow: visible;
    border-radius: var(--radius-sm);
  }

  .zoom-actions .zoom-reset,
  .zoom-actions :global(.icon-button-wrap button) {
    width: 2.35rem;
    height: 2.35rem;
    min-height: 2.35rem;
    padding: 0;
    border-radius: 0;
    background: var(--color-canvas);
  }

  .zoom-actions .zoom-reset {
    width: 3.8rem;
    color: var(--color-ink-muted);
    font-size: 0.7rem;
    font-variant-numeric: tabular-nums;
  }

  .zoom-actions :global(.icon-button-wrap:first-child button) {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  }

  .zoom-actions :global(.icon-button-wrap:last-child button) {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }

  .zoom-actions .zoom-reset,
  .zoom-actions :global(.icon-button-wrap:last-child) {
    margin-left: -1px;
  }

  .zoom-actions .zoom-reset:hover,
  .zoom-actions .zoom-reset:focus-visible,
  .zoom-actions :global(.icon-button-wrap button:hover),
  .zoom-actions :global(.icon-button-wrap button:focus-visible) {
    position: relative;
    z-index: 1;
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  @media (max-width: 56rem) {
    .viewer-header {
      align-items: flex-start;
      flex-direction: column;
    }

    h2 {
      max-width: calc(100vw - 2rem);
    }

    .viewer-actions {
      width: 100%;
      flex-wrap: wrap;
    }

  }
</style>
