<script lang="ts">
  let { index, label, sublabel = '', selected = false, onclick, image }: { index: number; label: string; sublabel?: string; selected?: boolean; onclick?: ()=>void; image?: string } = $props();
</script>
<button class="v2-asset-tile" class:selected onclick={onclick} type="button">
  <span class="v2-asset-check" aria-hidden="true">{selected ? '✓' : ''}</span>
  {#if image}<img src={image} alt="">{/if}
  <span class="v2-asset-meta"><b>{label}</b>{#if sublabel}<small>{sublabel}</small>{/if}</span>
</button>
