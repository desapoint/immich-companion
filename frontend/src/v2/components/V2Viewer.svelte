<script lang="ts">
  import V2AssetViewer from './V2AssetViewer.svelte';
  import V2RestoreViewer from './V2RestoreViewer.svelte';

  let {
    open = false,
    mode = 'assets',
    assetId = null,
    assetIds = [],
    onclose,
  }: {
    open?: boolean;
    title?: string;
    mode?: 'assets' | 'restore' | 'duplicates';
    assetId?: string | null;
    assetIds?: string[];
    onclose: () => void;
  } = $props();
</script>

{#if mode === 'restore'}
  <V2RestoreViewer {open} {assetId} {assetIds} {onclose} />
{:else}
  <V2AssetViewer {open} {assetId} {assetIds} {onclose} />
{/if}
