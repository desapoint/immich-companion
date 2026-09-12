<script lang="ts">
  let {
    children,
    compact = false,
    layout = 'auto',
    class: className = '',
  }: {
    children: import('svelte').Snippet;
    compact?: boolean;
    layout?: 'auto' | 'fixed';
    class?: string;
  } = $props();
</script>

<div class="v2-table-wrap">
  <table
    class={`v2-table ${className}`.trim()}
    data-compact={compact || undefined}
    data-layout={layout}
  >
    {@render children()}
  </table>
</div>
