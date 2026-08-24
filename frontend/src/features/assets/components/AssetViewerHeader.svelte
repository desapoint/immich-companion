<script lang="ts">
  import type { ViewerScaleMode } from '../types/assets';
  import AssetKeyboardHelp from './AssetKeyboardHelp.svelte';

  interface Props {
    filename: string;
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
    <span>Asset viewer</span>
    <h2 id="asset-viewer-title" title={filename}>{filename}</h2>
  </div>

  <div class="viewer-actions">
    <button class:selected class="selection-action" type="button" onclick={ontoggleselection} aria-pressed={selected}>
      {selected ? '✓ Selected' : 'Select image'}
    </button>
    <button type="button" onclick={ontogglescale} aria-pressed={scaleMode === 'actual'} title="Toggle between fit-to-screen and actual-size viewing">
      {scaleMode === 'fit' ? 'Actual size' : 'Fit to screen'}
    </button>
    <div class="zoom-actions" aria-label="Image zoom controls">
      <button type="button" onclick={onzoomout} aria-label="Zoom out" title="Zoom out (-)">−</button>
      <button type="button" onclick={onzoomreset} title="Reset zoom (0)">{zoomPercent}%</button>
      <button type="button" onclick={onzoomin} aria-label="Zoom in" title="Zoom in (+)">+</button>
    </div>
    <button type="button" onclick={ontoggleinfo} aria-pressed={infoOpen}>More info</button>
    <div class="help-action">
      <button type="button" onclick={ontogglehelp} aria-pressed={helpOpen} title="Show or hide keyboard shortcuts">
        Keyboard
      </button>
      {#if helpOpen}<AssetKeyboardHelp />{/if}
    </div>
    <button class="close-action" type="button" onclick={onclose} aria-label="Close asset viewer" title="Close viewer">×</button>
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

  button:hover,
  button[aria-pressed='true'] {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  .selection-action.selected {
    color: var(--color-positive-ink);
    border-color: var(--color-positive-border);
    background: var(--color-positive-surface);
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

  .zoom-actions button:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  }

  .zoom-actions button:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }

  .zoom-actions button + button {
    margin-left: -1px;
  }

  .close-action {
    display: grid;
    width: 2.3rem;
    padding: 0;
    place-items: center;
    color: var(--color-negative-ink);
    font-size: 1.3rem;
    line-height: 1;
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

    .close-action {
      margin-left: auto;
    }
  }
</style>
