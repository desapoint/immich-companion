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

  const toneClass = $derived(tone === 'default' ? '' : `v2-badge-${tone}`);
</script>

<span class={`v2-badge ${toneClass} ${className}`.trim()}>{text}{#if children}{@render children()}{/if}</span>
