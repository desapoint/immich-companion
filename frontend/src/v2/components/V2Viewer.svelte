<script lang="ts">
  import V2AssetViewer from './V2AssetViewer.svelte';
  import V2RestoreViewer from './V2RestoreViewer.svelte';

  let {
    open = false,
    mode = 'assets',
    onclose,
  }: {
    open?: boolean;
    title?: string;
    mode?: 'assets' | 'restore' | 'duplicates';
    onclose: () => void;
  } = $props();
</script>

{#if mode === 'restore'}
  <V2RestoreViewer {open} {onclose} />
{:else}
  <V2AssetViewer {open} {onclose} />
{/if}
