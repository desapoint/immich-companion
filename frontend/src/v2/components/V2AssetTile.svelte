<script lang="ts">
  import { Eye, Heart } from '@lucide/svelte';
  import V2AssetMetaPill from './V2AssetMetaPill.svelte';
  import V2LazyAssetMedia from './V2LazyAssetMedia.svelte';
  import V2RoundCheckbox from './V2RoundCheckbox.svelte';
  import type { MediaResource } from '../data/contracts';
  import type { ThumbnailSource } from '../data/mediaThumbnailCache';

  let {
    index,
    assetId = index,
    label,
    sublabel = '',
    favorite = false,
    tags = [],
    albums = [],
    stackCount = 0,
    selected = false,
    selectionMode = false,
    onactivate,
    onselect,
    onpreview,
    onpointerdown,
    image,
  }: {
    index: number;
    assetId?: string | number;
    label: string;
    sublabel?: string;
    favorite?: boolean;
    tags?: string[];
    albums?: string[];
    stackCount?: number;
    selected?: boolean;
    selectionMode?: boolean;
    onactivate?: (event: MouseEvent) => void;
    onselect?: (event: MouseEvent) => void;
    onpreview?: () => void;
    onpointerdown?: (event: PointerEvent) => void;
    image?: ThumbnailSource | (() => ThumbnailSource);
  } = $props();

  const visualVariant = $derived(String(index % 3));
  const cacheKey = $derived(`asset-thumbnail:${String(assetId)}`);
  const hasPills = $derived(favorite || tags.length > 0 || albums.length > 0 || stackCount > 0);
  const resolveImage = $derived((): ThumbnailSource => {
    if (typeof image === 'function') return image();
    return image ?? ({ url:'', fallbackUrls:[], mimeType:null, posterUrl:null, delivery:'thumbnail', originalMimeType:null, expiresAt:null } satisfies MediaResource);
  });
</script>

<div class="v2-asset-tile" class:selected class:selection-mode={selectionMode} class:has-pills={hasPills} data-variant={visualVariant} data-asset-id={String(assetId)}>
  <button class="v2-asset-main" type="button" aria-label={selectionMode ? `${selected ? 'Deselect' : 'Select'} ${label}` : `Preview ${label}`} aria-pressed={selectionMode ? selected : undefined} onclick={onactivate} onpointerdown={onpointerdown} ondragstart={(event) => event.preventDefault()}>
    <V2LazyAssetMedia {cacheKey} resolve={resolveImage} alt=""/>
    <span class="v2-asset-meta"><b>{label}</b>{#if sublabel}<small>{sublabel}</small>{/if}</span>
  </button>

  {#if hasPills}
    <div class="v2-asset-pill-row" aria-label="Asset metadata">
      {#if favorite}<span class="v2-asset-favorite-pill" aria-label="Favorite"><Heart size={12} fill="currentColor" aria-hidden="true"/></span>{/if}
      {#if albums.length}<V2AssetMetaPill kind="albums" count={albums.length} items={albums}/>{/if}
      {#if tags.length}<V2AssetMetaPill kind="tags" count={tags.length} items={tags}/>{/if}
      {#if stackCount>0}<V2AssetMetaPill kind="stack" count={stackCount}/>{/if}
    </div>
  {/if}

  <span class="v2-asset-checkbox-zone"><V2RoundCheckbox checked={selected} ariaLabel={`${selected ? 'Deselect' : 'Select'} ${label}`} onclick={onselect}/></span>
  <button class="v2-asset-preview-zone" class:visible={selectionMode} type="button" aria-label={`Preview ${label}`} title="Preview" tabindex={selectionMode ? 0 : -1} disabled={!selectionMode} onclick={(event) => {event.stopPropagation();onpreview?.();}} onpointerdown={(event) => event.stopPropagation()}>
    <Eye size={17} aria-hidden="true" />
  </button>
</div>
