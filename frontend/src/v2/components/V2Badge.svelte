<script lang="ts">
  let {
    tone = 'default',
    text = '',
    children,
    class: className = '',
    onclick,
    title,
    ariaLabel,
  }: {
    tone?: 'default' | 'ok' | 'warn' | 'bad';
    text?: string;
    children?: import('svelte').Snippet;
    class?: string;
    onclick?: (event: MouseEvent) => void;
    title?: string;
    ariaLabel?: string;
  } = $props();
</script>

{#if onclick}
  <button type="button" class={`v2-badge ${className}`.trim()} data-tone={tone} {onclick} {title} aria-label={ariaLabel ?? title ?? text}>{text}{#if children}{@render children()}{/if}</button>
{:else}
  <span class={`v2-badge ${className}`.trim()} data-tone={tone}>{text}{#if children}{@render children()}{/if}</span>
{/if}
