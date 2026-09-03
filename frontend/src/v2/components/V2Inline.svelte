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
</script>

<div class={`v2-inline v2-inline-${gap} v2-inline-${justify} v2-inline-align-${align}${wrap ? ' v2-inline-wrap' : ''}`}>
  {@render children()}
</div>
