<script lang="ts">
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import type { ViewerScaleMode } from '../types/assets';
  import AssetKeyboardHelp from './AssetKeyboardHelp.svelte';

  interface Props {
    filename: string;
    selectedFilename: string;
    selected: boolean;
    scaleMode: ViewerScaleMode;
    infoOpen: boolean;
    helpOpen: boolean;
    zoomPercent: number;
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
  </div>

  <div class="viewer-actions">
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
    <div class="zoom-actions" aria-label="Image zoom controls">
      <IconButton icon="zoom-out" label="Zoom out (-)" size="compact" onclick={onzoomout} />
      <button type="button" onclick={onzoomreset} title="Reset zoom (0)">{zoomPercent}%</button>
      <IconButton icon="zoom-in" label="Zoom in (+)" size="compact" onclick={onzoomin} />
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
  }

  .zoom-actions button {
    min-width: 2.2rem;
    border-radius: 0;
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
      overflow-x: auto;
      padding-bottom: 0.15rem;
    }

  }
</style>
