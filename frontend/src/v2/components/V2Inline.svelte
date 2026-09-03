<script lang="ts">
  let {
    gap = 'md',
    justify = 'start',
    align = 'center',
    wrap = false,
    children,
  }: {
    gap?: 'xs' | 'sm' | 'md' | 'lg';
    justify?: 'start' | 'between' | 'end';
    align?: 'start' | 'center' | 'end';
    wrap?: boolean;
    children: import('svelte').Snippet;
  } = $props();

  const gaps = {
    xs: 'var(--v2-space-1)',
    sm: 'var(--v2-space-2)',
    md: 'var(--v2-space-3)',
    lg: 'var(--v2-space-4)',
  } as const;
  const justifications = { start: 'flex-start', between: 'space-between', end: 'flex-end' } as const;
  const alignments = { start: 'flex-start', center: 'center', end: 'flex-end' } as const;
</script>

<div class="v2-inline" style={`gap:${gaps[gap]};justify-content:${justifications[justify]};align-items:${alignments[align]};flex-wrap:${wrap ? 'wrap' : 'nowrap'}`}>
  {@render children()}
</div>
