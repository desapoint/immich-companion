<script lang="ts">
  let { children, class: className = '' }: { children?: import('svelte').Snippet; class?: string } = $props();
</script>

<div class={`v2-notice ${className}`.trim()}>{#if children}{@render children()}{/if}</div>
