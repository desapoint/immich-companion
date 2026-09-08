<script lang="ts">
  import { Folder, Layers3, Tags } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { floatingFieldLayout } from '../state/floatingField';

  let {
    kind,
    count,
    items = [],
  }: {
    kind: 'albums' | 'tags' | 'stack';
    count: number;
    items?: string[];
  } = $props();

  let open = $state(false);
  let anchor = $state<HTMLSpanElement>();
  let popup = $state<HTMLDivElement>();
  let popupTop = $state(0);
  let popupBottom = $state<number|null>(null);
  let popupLeft = $state(0);
  let popupWidth = $state(240);
  let popupMaxHeight = $state(220);
  let closeTimer: ReturnType<typeof setTimeout> | undefined;

  const title = $derived(kind === 'albums' ? 'Albums' : kind === 'tags' ? 'Tags' : 'Stack');
  const ariaLabel = $derived(kind === 'stack' ? `${count} assets in stack` : `${count} ${kind}`);

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy() { node.remove(); } };
  }

  function cancelClose() {
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = undefined;
  }

  function scheduleClose() {
    cancelClose();
    closeTimer = setTimeout(() => { open = false; }, 110);
  }

  function positionPopup() {
    if (!open || !anchor) return;
    const rect = anchor.getBoundingClientRect();
    const layout = floatingFieldLayout({
      anchor: rect,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      preferredWidth: 240,
      preferredHeight: 220,
      minimumUsefulHeight: 96,
      minimumHeight: 72,
    });
    popupTop = layout.placement === 'down' ? layout.top : 0;
    popupBottom = layout.placement === 'up' ? Math.max(10, window.innerHeight - rect.top + 5) : null;
    popupLeft = layout.left;
    popupWidth = layout.width;
    popupMaxHeight = layout.maxHeight;
  }

  function show() {
    cancelClose();
    open = true;
    void tick().then(() => {
      positionPopup();
      requestAnimationFrame(positionPopup);
    });
  }

  $effect(() => {
    if (!open) return;
    const reposition = () => positionPopup();
    const handleScroll = (event: Event) => {
      const target = event.target;
      if (target instanceof Node && popup?.contains(target)) return;
      reposition();
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', handleScroll, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', handleScroll, true);
    };
  });
</script>

<span
  bind:this={anchor}
  class="v2-asset-meta-pill"
  data-kind={kind}
  aria-label={ariaLabel}
  onpointerenter={show}
  onpointerleave={scheduleClose}
>
  {#if kind === 'albums'}<Folder size={12} aria-hidden="true"/>{:else if kind === 'tags'}<Tags size={12} aria-hidden="true"/>{:else}<Layers3 size={12} aria-hidden="true"/>{/if}
  <span>{count}</span>
</span>

{#if open}
  <div
    use:portal
    bind:this={popup}
    class="v2-asset-meta-popover"
    role="tooltip"
    style={`top:${popupBottom===null?`${popupTop}px`:'auto'};bottom:${popupBottom===null?'auto':`${popupBottom}px`};left:${popupLeft}px;width:${popupWidth}px;max-height:${popupMaxHeight}px`}
    onpointerenter={cancelClose}
    onpointerleave={scheduleClose}
  >
    <strong>{title}</strong>
    {#if kind === 'stack'}
      <span class="v2-asset-meta-popover-summary">{count} asset{count === 1 ? '' : 's'} in this stack</span>
    {:else}
      <div class="v2-asset-meta-popover-list">
        {#each items as item (item)}<span>{item}</span>{/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .v2-asset-meta-pill{display:inline-flex;align-items:center;gap:3px;min-height:18px;padding:1px 5px;border:1px solid rgba(255,255,255,.24);border-radius:999px;background:rgba(10,15,21,.72);color:#f4f7fb;font-size:10px;font-weight:700;line-height:1;box-shadow:0 1px 3px rgba(0,0,0,.2);pointer-events:auto}
  .v2-asset-meta-pill svg{flex:0 0 auto}
  .v2-asset-meta-popover{position:fixed;z-index:220;display:grid;gap:7px;overflow:hidden;padding:8px;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-surface-2);color:var(--v2-text);box-shadow:0 14px 32px rgba(0,0,0,.34);font:inherit;font-size:11px;line-height:1.35}
  .v2-asset-meta-popover strong{font-size:11px}
  .v2-asset-meta-popover-summary{color:var(--v2-muted)}
  .v2-asset-meta-popover-list{display:grid;gap:2px;overflow-y:auto;max-height:inherit;padding:1px 0;scrollbar-gutter:stable both-edges;scrollbar-width:thin;scrollbar-color:#475970 transparent}
  .v2-asset-meta-popover-list::-webkit-scrollbar{width:6px;height:6px}
  .v2-asset-meta-popover-list::-webkit-scrollbar-track{background:transparent}
  .v2-asset-meta-popover-list::-webkit-scrollbar-thumb{border:1px solid var(--v2-surface-2);border-radius:999px;background:#475970}
  .v2-asset-meta-popover-list span{padding:4px 5px;border-radius:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-asset-meta-popover-list span:hover{background:#172231}
</style>