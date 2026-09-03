<script lang="ts">
  let {
    children,
    compact = false,
  }: {
    children: import('svelte').Snippet;
    compact?: boolean;
  } = $props();
</script>

<div class="v2-table-wrap">
  <table class="v2-table" data-compact={compact || undefined}>
    {@render children()}
  </table>
</div>
