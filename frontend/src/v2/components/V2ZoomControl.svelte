<script lang="ts">
  import { ZoomIn, ZoomOut } from '@lucide/svelte';

  let {
    value,
    onzoomout,
    onzoomin,
  }: {
    value: number;
    onzoomout: () => void;
    onzoomin: () => void;
  } = $props();
</script>

<div class="v2-zoom-control" role="group" aria-label="Zoom controls">
  <button type="button" class="v2-zoom-control-button" onclick={onzoomout} title="Zoom out" aria-label="Zoom out">
    <ZoomOut size={16} strokeWidth={2} />
  </button>
  <output class="v2-zoom-control-value" aria-live="polite">{Math.round(value * 100)}%</output>
  <button type="button" class="v2-zoom-control-button" onclick={onzoomin} title="Zoom in" aria-label="Zoom in">
    <ZoomIn size={16} strokeWidth={2} />
  </button>
</div>

<style>
  .v2-zoom-control{display:inline-grid;grid-template-columns:36px minmax(58px,auto) 36px;align-items:stretch;height:36px;border:1px solid var(--v2-line);border-radius:9px;overflow:hidden;background:var(--v2-surface);color:var(--v2-text)}
  .v2-zoom-control-button{display:grid;place-items:center;border:0;border-right:1px solid var(--v2-line);padding:0;background:transparent;color:inherit;cursor:pointer}
  .v2-zoom-control-button:last-child{border-right:0;border-left:1px solid var(--v2-line)}
  .v2-zoom-control-button:hover{background:var(--v2-surface-2)}
  .v2-zoom-control-button:focus-visible{position:relative;z-index:1;outline:2px solid #4169a8;outline-offset:-2px}
  .v2-zoom-control-button svg{display:block}
  .v2-zoom-control-value{display:grid;place-items:center;min-width:0;padding:0 8px;font-size:12px;font-weight:750;line-height:1;font-variant-numeric:tabular-nums;color:var(--v2-text)}
</style>
