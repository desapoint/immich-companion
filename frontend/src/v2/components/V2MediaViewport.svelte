<script module lang="ts">
  export function nextMediaSourceIndex(current: number, count: number): number | null {
    return current + 1 < count ? current + 1 : null;
  }
</script>

<script lang="ts">
  import type { AssetRecord, MediaResource } from '../data/contracts';
  import V2ImageViewport from './V2ImageViewport.svelte';
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
  const sources = $derived([...new Set([resource.url, ...resource.fallbackUrls].filter(Boolean))]);
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
  <!-- svelte-ignore a11y_media_has_caption -->
  <video
    class="v2-video-player"
    controls
    playsinline
    preload="metadata"
    poster={resource.posterUrl ?? undefined}
    aria-label={alt}
    src={source}
    onerror={sourceFailed}
  >
    Your browser cannot play the compatible video stream.
  </video>
{:else}
  <V2ImageViewport src={source} {alt} {controller} onerror={sourceFailed}/>
{/if}

<style>
  .v2-video-player { width:100%; height:100%; object-fit:contain; background:#000; }
</style>
