<script lang="ts">
  import V2AssetViewer from './V2AssetViewer.svelte';
  import V2RestoreViewer from './V2RestoreViewer.svelte';
  import type { ViewerNavigationWindow } from '../data/contracts';

  let {
    open = false,
    mode = 'assets',
    assetId = null,
    assetIds = [],
    onclose,
    onnavigate,
    onfilterrelation,
  }: {
    open?: boolean;
    title?: string;
    mode?: 'assets' | 'restore' | 'duplicates';
    assetId?: string | null;
    assetIds?: string[];
    onclose: () => void;
    onnavigate?: (assetId: string, navigation: ViewerNavigationWindow) => void | Promise<void>;
    onfilterrelation?: (kind: 'album' | 'tag', id: string) => void | Promise<void>;
  } = $props();
</script>

{#if mode === 'restore'}
  <V2RestoreViewer {open} {assetId} {assetIds} {onclose} {onnavigate} />
{:else}
  <V2AssetViewer {open} {assetId} {assetIds} {onclose} {onnavigate} {onfilterrelation} />
{/if}
