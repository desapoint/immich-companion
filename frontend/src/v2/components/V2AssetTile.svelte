<script lang="ts">
  import { Eye, ImageOff } from '@lucide/svelte';
  import V2RoundCheckbox from './V2RoundCheckbox.svelte';
  import type { MediaResource } from '../data/contracts';

  let {
    index,
    assetId = index,
    label,
    sublabel = '',
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
    selected?: boolean;
    selectionMode?: boolean;
    onactivate?: (event: MouseEvent) => void;
    onselect?: (event: MouseEvent) => void;
    onpreview?: () => void;
    onpointerdown?: (event: PointerEvent) => void;
    image?: string | MediaResource;
  } = $props();

  const visualVariant = $derived(String(index % 3));
  const imageUrl = $derived(typeof image === 'string' ? image : image?.url ?? '');
  const videoSource = $derived(Boolean(imageUrl && /\.(mp4|webm)(?:$|\?)/i.test(imageUrl)));
  let mediaFailed = $state(false);
  $effect(() => { imageUrl; mediaFailed = false; });
</script>

<div class="v2-asset-tile" class:selected class:selection-mode={selectionMode} data-variant={visualVariant} data-asset-id={String(assetId)}>
  <button class="v2-asset-main" type="button" aria-label={selectionMode ? `${selected ? 'Deselect' : 'Select'} ${label}` : `Preview ${label}`} aria-pressed={selectionMode ? selected : undefined} onclick={onactivate} onpointerdown={onpointerdown} ondragstart={(event) => event.preventDefault()}>
    {#if mediaFailed || !imageUrl}<span class="v2-asset-media-unavailable" aria-label="Thumbnail unavailable"><ImageOff size={26} aria-hidden="true"/><small>Preview unavailable</small></span>{:else if videoSource}<video src={imageUrl} muted playsinline preload="metadata" aria-hidden="true" onerror={()=>mediaFailed=true}></video>{:else}<img src={imageUrl} alt="" loading="lazy" decoding="async" onerror={()=>mediaFailed=true}>{/if}
    <span class="v2-asset-meta"><b>{label}</b>{#if sublabel}<small>{sublabel}</small>{/if}</span>
  </button>
  <span class="v2-asset-checkbox-zone"><V2RoundCheckbox checked={selected} ariaLabel={`${selected ? 'Deselect' : 'Select'} ${label}`} onclick={onselect}/></span>
  <button class="v2-asset-preview-zone" class:visible={selectionMode} type="button" aria-label={`Preview ${label}`} title="Preview" tabindex={selectionMode ? 0 : -1} disabled={!selectionMode} onclick={(event) => {event.stopPropagation();onpreview?.();}} onpointerdown={(event) => event.stopPropagation()}>
    <Eye size={17} aria-hidden="true" />
  </button>
</div>

<style>
  .v2-asset-main video { width:100%; height:100%; object-fit:cover; display:block; }
  .v2-asset-media-unavailable { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:.35rem; opacity:.65; background:color-mix(in srgb,var(--v2-surface,Canvas) 88%,currentColor 12%); }
  .v2-asset-media-unavailable small { font-size:.72rem; }
</style>
