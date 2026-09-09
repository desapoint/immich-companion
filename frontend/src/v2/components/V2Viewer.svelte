<script lang="ts">
  import V2AssetViewer from './V2AssetViewer.svelte';
  import V2RestoreViewer from './V2RestoreViewer.svelte';
  import type { ViewerNavigationWindow } from '../data/contracts';

  let {
    open = false,
    mode = 'assets',
    assetId = null,
    assetIds = [],
    resultMode = 'Pagination',
    collectionPage = 1,
    collectionPageSize = 24,
    collectionTotal = 0,
    startStack = false,
    restoreBusy = false,
    onclose,
    onnavigate,
    onmutated,
    onrestore,
    onfilterrelation,
    isselected,
    ontoggleselection,
  }: {
    open?: boolean;
    title?: string;
    mode?: 'assets' | 'restore' | 'duplicates';
    assetId?: string | null;
    assetIds?: string[];
    resultMode?: 'Pagination' | 'Infinite';
    collectionPage?: number;
    collectionPageSize?: number;
    collectionTotal?: number;
    startStack?: boolean;
    restoreBusy?: boolean;
    onclose: () => void;
    onnavigate?: (assetId: string, navigation: ViewerNavigationWindow) => void | Promise<void>;
    onmutated?: () => void | Promise<void>;
    onrestore?: (assetId: string) => boolean | Promise<boolean>;
    onfilterrelation?: (kind: 'album' | 'tag', id: string) => void | Promise<void>;
    isselected?: (assetId: string) => boolean;
    ontoggleselection?: (assetId: string) => void;
  } = $props();
</script>

{#if mode === 'restore'}
  <V2RestoreViewer {open} {assetId} {assetIds} {restoreBusy} {onclose} {onnavigate} {onrestore} />
{:else}
  <V2AssetViewer {open} {assetId} {assetIds} {resultMode} {collectionPage} {collectionPageSize} {collectionTotal} {startStack} {onclose} {onnavigate} {onmutated} {onfilterrelation} {isselected} {ontoggleselection} />
{/if}
