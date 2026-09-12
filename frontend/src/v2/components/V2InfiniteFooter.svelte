<script lang="ts">
  import V2Button from './V2Button.svelte';

  let {
    loaded,
    total,
    batchSize,
    onloadmore,
    noun = 'items',
  }: {
    loaded: number;
    total: number;
    batchSize: number;
    onloadmore?: () => void;
    noun?: string;
  } = $props();

  const done = $derived(loaded >= total);
</script>

<div class="v2-infinite-sentinel" data-loading={!done || undefined}>
  <div>{done ? `All ${total.toLocaleString()} matching ${noun} loaded` : `${loaded.toLocaleString()} of ${total.toLocaleString()} loaded`}</div>
  {#if !done}<V2Button onclick={onloadmore}>Load next {batchSize}</V2Button>{/if}
</div>
