<script lang="ts">
  let {
    gap = 'md',
    children,
  }: {
    gap?: 'xs' | 'sm' | 'md' | 'lg';
    children: import('svelte').Snippet;
  } = $props();

  const gaps = {
    xs: 'var(--v2-space-1)',
    sm: 'var(--v2-space-2)',
    md: 'var(--v2-space-3)',
    lg: 'var(--v2-space-4)',
  } as const;
</script>

<div class="v2-stack" style={`gap:${gaps[gap]}`}>
  {@render children()}
</div>
