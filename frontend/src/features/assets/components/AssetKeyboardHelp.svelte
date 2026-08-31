<script lang="ts">
  interface Props { duplicateMode?: boolean; }
  let { duplicateMode = false }: Props = $props();
</script>

<div class="keyboard-help" role="tooltip" aria-label="Viewer keyboard shortcuts">
  <strong>Keyboard shortcuts</strong>
  <dl>
    <div><dt><kbd>Space</kbd></dt><dd>Toggle selection</dd></div>
    <div><dt><kbd>←</kbd> / <kbd>H</kbd></dt><dd>Previous image</dd></div>
    <div><dt><kbd>→</kbd> / <kbd>L</kbd></dt><dd>Next image</dd></div>
    {#if duplicateMode}
      <div><dt><kbd>K</kbd></dt><dd>Use viewed copy as primary</dd></div>
      <div><dt><kbd>R</kbd></dt><dd>Resolve duplicate group</dd></div>
      <div><dt><kbd>S</kbd></dt><dd>Stack all copies</dd></div>
      <div><dt><kbd>X</kbd></dt><dd>Skip / review later</dd></div>
    {/if}
    <div><dt><kbd>I</kbd></dt><dd>Toggle more info</dd></div>
    <div><dt><kbd>M</kbd></dt><dd>Toggle image size</dd></div>
    <div><dt><kbd>+</kbd> / <kbd>−</kbd></dt><dd>Zoom in or out</dd></div>
    <div><dt><kbd>0</kbd></dt><dd>Reset zoom</dd></div>
    <div><dt>Wheel</dt><dd>Scroll the image</dd></div>
    <div><dt><kbd>Ctrl</kbd> + Wheel</dt><dd>Zoom at the pointer</dd></div>
    <div><dt>Drag</dt><dd>Pan the zoomed image</dd></div>
    <div><dt><kbd>?</kbd></dt><dd>Toggle shortcuts</dd></div>
    <div><dt><kbd>Esc</kbd> / <kbd>Q</kbd></dt><dd>Close viewer</dd></div>
  </dl>
</div>

<style>
  .keyboard-help {
    position: absolute;
    z-index: 20;
    top: calc(100% + 0.5rem);
    right: 0;
    width: min(20rem, calc(100vw - 1rem));
    max-height: min(28rem, calc(100dvh - 5rem));
    padding: 0.85rem;
    overflow: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 1rem 2.5rem rgb(0 0 0 / 24%);
  }

  strong {
    font-size: 0.82rem;
  }

  dl {
    display: grid;
    gap: 0.48rem;
    margin: 0.7rem 0 0;
  }

  dl div {
    display: grid;
    grid-template-columns: 6rem 1fr;
    gap: 0.6rem;
    align-items: center;
  }

  dt,
  dd {
    margin: 0;
    font-size: 0.7rem;
  }

  dd {
    color: var(--color-ink-muted);
  }

  kbd {
    padding: 0.15rem 0.32rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 0.28rem;
    background: var(--color-surface-soft);
    box-shadow: 0 0.1rem 0 var(--color-border-strong);
    font-family: var(--font-mono);
    font-size: 0.65rem;
  }
</style>
