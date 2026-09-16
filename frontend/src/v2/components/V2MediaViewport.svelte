<script lang="ts">
  import type { AssetRecord, MediaResource } from '../data/contracts';
  import { mediaResourceSources, nextMediaSourceIndex } from '../data/mediaSources';
  import V2ImageViewport from './V2ImageViewport.svelte';
  import V2VideoPlayer from './V2VideoPlayer.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';

  let {
    resource,
    assetType,
    alt,
    controller = new ViewerViewportController(),
    onerror,
  }: {
    resource: MediaResource;
    assetType: AssetRecord['asset_type'];
    alt: string;
    controller?: ViewerViewportController;
    onerror?: () => void;
  } = $props();

  let sourceSelection = $state({ key: '', index: 0 });
  const sources = $derived(mediaResourceSources(resource));
  const sourceKey = $derived(sources.join('\u0000'));
  const sourceIndex = $derived(sourceSelection.key === sourceKey ? sourceSelection.index : 0);
  const source = $derived(sources[sourceIndex] ?? '');

  function sourceFailed(): void {
    const next = nextMediaSourceIndex(sourceIndex, sources.length);
    if (next !== null) {
      sourceSelection = { key: sourceKey, index: next };
      return;
    }
    onerror?.();
  }
</script>

{#if assetType === 'VIDEO'}
  {#key source}
    <V2VideoPlayer src={source} poster={resource.posterUrl} label={alt} onerror={sourceFailed}/>
  {/key}
{:else}
  <V2ImageViewport src={source} {alt} {controller} onerror={sourceFailed}/>
{/if}
