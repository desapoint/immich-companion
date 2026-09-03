<script lang="ts">
  let { items, active = items[0], onselect }: { items: string[]; active?: string; onselect?: (item:string)=>void } = $props();
</script>
<div class="v2-tabs" role="tablist">
  {#each items as item}<button class:active={item===active} class="v2-tab" role="tab" aria-selected={item===active} onclick={()=>onselect?.(item)}>{item}</button>{/each}
</div>
