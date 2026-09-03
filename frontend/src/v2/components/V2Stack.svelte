<script lang="ts">
  let {
    gap = 'md',
    children,
  }: {
    gap?: 'xs' | 'sm' | 'md' | 'lg';
    children: import('svelte').Snippet;
  } = $props();
</script>

<div class={`v2-stack v2-stack-${gap}`}>
  {@render children()}
</div>
