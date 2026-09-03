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
</script>

{#if kind === 'badge'}
  <span class={`v2-badge ${tone === 'default' ? '' : tone}`}>{value}{#if children}{@render children()}{/if}</span>
{:else if kind === 'metric'}
  <div class="v2-card v2-metric"><b>{value}</b><span>{title}</span></div>
{:else if kind === 'notice'}
  <div class="v2-notice">{#if children}{@render children()}{/if}</div>
{:else if kind === 'section'}
  <section class="v2-section">
    {#if title}<div class="v2-section-title"><h3>{title}</h3></div>{/if}
    {#if children}{@render children()}{/if}
  </section>
{:else}
  <div class="v2-card">{#if children}{@render children()}{/if}</div>
{/if}
