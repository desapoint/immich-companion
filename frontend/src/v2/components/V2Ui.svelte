<script lang="ts">
  let {
    kind = 'card',
    tone = 'default',
    title = '',
    value = '',
    children,
  }: {
    kind?: 'card' | 'notice' | 'badge' | 'metric' | 'section';
    tone?: 'default' | 'ok' | 'warn' | 'bad';
    title?: string;
    value?: string;
    children?: import('svelte').Snippet;
  } = $props();

  const toneClass = $derived(tone === 'default' ? '' : `v2-badge-${tone}`);
</script>

{#if kind === 'badge'}
  <span class={`v2-badge ${toneClass}`.trim()}>{value}{#if children}{@render children()}{/if}</span>
{:else if kind === 'metric'}
  <div class="v2-card"><span class="v2-metric-value">{value}</span><span class="v2-metric-label">{title}</span></div>
{:else if kind === 'notice'}
  <div class="v2-notice">{#if children}{@render children()}{/if}</div>
{:else if kind === 'section'}
  <section class="v2-section">
    {#if title}<div class="v2-section-header"><h3 class="v2-section-heading">{title}</h3></div>{/if}
    {#if children}{@render children()}{/if}
  </section>
{:else}
  <div class="v2-card">{#if children}{@render children()}{/if}</div>
{/if}
