<script lang="ts">
  export let kind: 'card' | 'notice' | 'badge' | 'metric' | 'section' = 'card';
  export let tone: 'default' | 'ok' | 'warn' | 'bad' = 'default';
  export let title = '';
  export let value = '';
</script>

{#if kind === 'badge'}
  <span class={`v2-badge ${tone === 'default' ? '' : tone}`}>{value}<slot /></span>
{:else if kind === 'metric'}
  <div class="v2-card v2-metric"><b>{value}</b><span>{title}</span></div>
{:else if kind === 'notice'}
  <div class="v2-notice"><slot /></div>
{:else if kind === 'section'}
  <section class="v2-section">
    {#if title}<div class="v2-section-title"><h3>{title}</h3></div>{/if}
    <slot />
  </section>
{:else}
  <div class="v2-card"><slot /></div>
{/if}
