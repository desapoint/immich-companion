<script lang="ts">
  import { Check } from '@lucide/svelte';
  import { foregroundForBackground, normalizeHex } from '../state/color';

  let {
    color,
    size = 'md',
    selected = false,
    decorative = true,
  }: {
    color: string | null;
    size?: 'xs' | 'sm' | 'md';
    selected?: boolean;
    decorative?: boolean;
  } = $props();

  const normalized = $derived(color === null ? null : normalizeHex(color));
  const foreground = $derived(normalized ? foregroundForBackground(normalized) : '#FFFFFF');
</script>

<span
  class="v2-color-swatch"
  data-size={size}
  data-empty={normalized === null || undefined}
  data-selected={selected || undefined}
  style:--v2-swatch-color={normalized ?? 'transparent'}
  style:--v2-swatch-foreground={foreground}
  aria-hidden={decorative ? 'true' : undefined}
  aria-label={decorative ? undefined : normalized ?? 'No color'}
  role={decorative ? undefined : 'img'}
>
  {#if selected && normalized}<Check size={size === 'xs' ? 9 : size === 'sm' ? 12 : 15} strokeWidth={3} aria-hidden="true"/>{/if}
</span>

<style>
  .v2-color-swatch{position:relative;display:inline-grid;place-items:center;flex:0 0 auto;width:24px;height:24px;border-radius:6px;background:var(--v2-swatch-color);color:var(--v2-swatch-foreground);box-shadow:inset 0 0 0 1px rgba(0,0,0,.28),0 0 0 1px rgba(255,255,255,.13);overflow:hidden}
  .v2-color-swatch[data-size="xs"]{width:12px;height:12px;border-radius:3px}
  .v2-color-swatch[data-size="sm"]{width:18px;height:18px;border-radius:5px}
  .v2-color-swatch[data-selected="true"]{box-shadow:inset 0 0 0 1px rgba(0,0,0,.28),0 0 0 2px var(--v2-accent),0 0 0 3px #0b1016}
  .v2-color-swatch[data-empty="true"]{background:#111923;color:var(--v2-muted)}
  .v2-color-swatch[data-empty="true"]::after{content:"";position:absolute;width:140%;height:1px;background:#8090a3;transform:rotate(-45deg)}
  .v2-color-swatch :global(svg){display:block;filter:drop-shadow(0 1px 1px rgba(0,0,0,.35))}
</style>
