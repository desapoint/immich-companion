<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    side,
    split,
    children,
  }: {
    side: 'left' | 'right';
    split: number;
    children: Snippet;
  } = $props();

  const inset = $derived(side === 'left'
    ? `inset(0 ${100 - split}% 0 0)`
    : `inset(0 0 0 ${split}%)`);
</script>

<div class="comparison-rect-mask" style:clip-path={inset}>
  {@render children()}
</div>

<style>
  .comparison-rect-mask {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
  }
</style>
