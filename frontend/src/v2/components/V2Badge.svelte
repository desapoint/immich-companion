<script lang="ts">
  let {
    tone = 'default',
    text = '',
    children,
    class: className = '',
  }: {
    tone?: 'default' | 'ok' | 'warn' | 'bad';
    text?: string;
    children?: import('svelte').Snippet;
    class?: string;
  } = $props();
</script>

<span class={`v2-badge ${className}`.trim()} data-tone={tone}>{text}{#if children}{@render children()}{/if}</span>
