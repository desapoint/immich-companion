<script lang="ts">
  import { Folder, Layers3, Tags } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { floatingFieldLayout } from '../state/floatingField';

  let {
    kind,
    count,
    items = [],
    onclick,
  }: {
    kind: 'albums' | 'tags' | 'stack';
    count: number;
    items?: string[];
    onclick?: () => void;
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

  function activate(event: MouseEvent) {
    if (!onclick) return;
    event.preventDefault();
    event.stopPropagation();
    open = false;
    onclick();
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
  class:interactive={Boolean(onclick)}
  data-kind={kind}
  aria-label={ariaLabel}
  onpointerenter={show}
  onpointerleave={scheduleClose}
  onclick={activate}
  onpointerdown={(event)=>onclick&&event.stopPropagation()}
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
      <span class="v2-asset-meta-popover-summary">{count} asset{count === 1 ? '' : 's'} in this stack{onclick?' · Click to view':''}</span>
    {:else}
      <div class="v2-asset-meta-popover-list">
        {#each items as item (item)}<span>{item}</span>{/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .v2-asset-meta-pill{display:inline-flex;align-items:center;gap:3px;min-height:18px;padding:1px 5px;border:1px solid rgba(255,255,255,.24);border-radius:999px;background:rgba(10,15,21,.78);color:#f4f7fb;font-size:10px;font-weight:700;line-height:1;box-shadow:0 1px 3px rgba(0,0,0,.2);pointer-events:auto}
  .v2-asset-meta-pill.interactive{cursor:pointer}.v2-asset-meta-pill.interactive:hover{border-color:rgba(255,255,255,.55);background:rgba(22,31,43,.94)}
  .v2-asset-meta-pill svg{flex:0 0 auto}
  .v2-asset-meta-popover{position:fixed;z-index:10020;display:grid;gap:7px;overflow:hidden;padding:8px;border:1px solid var(--v2-line,#2a3544);border-radius:9px;background:var(--v2-surface-2,#17202b);color:var(--v2-text,#eef3f8);box-shadow:0 14px 32px rgba(0,0,0,.4);font-family:var(--font-sans,Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif);font-size:11px;font-weight:400;line-height:1.35}
  .v2-asset-meta-popover strong{font-size:11px;font-weight:700;color:var(--v2-text,#eef3f8)}
  .v2-asset-meta-popover-summary{color:var(--v2-muted,#91a1b4)}
  .v2-asset-meta-popover-list{display:flex;flex-wrap:wrap;align-content:flex-start;gap:5px;overflow-y:auto;max-height:inherit;padding:1px 0;scrollbar-gutter:stable;scrollbar-width:thin;scrollbar-color:#475970 transparent}
  .v2-asset-meta-popover-list::-webkit-scrollbar{width:6px;height:6px}
  .v2-asset-meta-popover-list::-webkit-scrollbar-track{background:transparent}
  .v2-asset-meta-popover-list::-webkit-scrollbar-thumb{border:1px solid var(--v2-surface-2,#17202b);border-radius:999px;background:#475970}
  .v2-asset-meta-popover-list span{display:inline-flex;align-items:center;max-width:100%;padding:3px 7px;border:1px solid var(--v2-line,#2a3544);border-radius:999px;background:var(--v2-surface,#111821);color:var(--v2-text,#eef3f8);font-size:10px;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-asset-meta-popover-list span:hover{border-color:#4d607a;background:#172231}
</style>
