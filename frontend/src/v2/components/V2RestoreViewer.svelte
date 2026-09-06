<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageViewport from './V2ImageViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { TrashAssetRecord } from '../data/contracts';

  let { open=false, assetId=null, assetIds=[], onclose }: { open?:boolean; assetId?:string|null; assetIds?:string[]; onclose:()=>void }=$props();
  const camera=new ViewerViewportController();
  let currentId=$state<string|null>(assetId),asset=$state<TrashAssetRecord|undefined>();
  $effect(()=>{if(assetId!==null)currentId=assetId});
  $effect(()=>{const id=currentId;if(!id){asset=undefined;return}void(async()=>asset=await libraryData.assets.getTrashById(id))()});
  const currentIndex=$derived(currentId?assetIds.indexOf(currentId):-1),media=$derived(asset?libraryData.media.view(asset):null),mediaSrc=$derived(media?.url??''),posterSrc=$derived(media?.posterUrl??(asset?libraryData.media.thumbnail(asset).url:'')),isVideo=$derived(asset?.type==='VIDEO'),canPrevious=$derived(currentIndex>0),canNext=$derived(currentIndex>=0&&currentIndex<assetIds.length-1),positionLabel=$derived(currentIndex>=0?`${currentIndex+1} / ${assetIds.length}`:'—');
  $effect(()=>{if(open&&!isVideo)requestAnimationFrame(()=>camera.fit())});
  function previous(){if(canPrevious)currentId=assetIds[currentIndex-1]}
  function next(){if(canNext)currentId=assetIds[currentIndex+1]}
  async function restore(){if(!asset)return;const fallback=assetIds[currentIndex+1]??assetIds[currentIndex-1]??null;await libraryData.assets.restore({kind:'ids',ids:[asset.id]});if(fallback&&await libraryData.assets.getTrashById(fallback))currentId=fallback;else onclose()}
</script>
<V2ViewerShell {open} title="Restore Viewer" {onclose}>
  {#snippet header()}<V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Restore Viewer</b><V2Badge text={positionLabel}/>{#if media?.delivery==='transcoded'}<V2Badge text="Transcoded playback"/>{:else if media?.delivery==='decoded'}<V2Badge text="Decoded preview"/>{/if}</V2Inline><V2Inline gap="sm">{#if !isVideo}<V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button>{/if}</V2Inline>{/snippet}
  <div class="v2-viewer-stage"><div class="v2-image-stage">{#if asset}{#if isVideo}<video class="v2-video-player" controls playsinline preload="metadata" poster={posterSrc} aria-label={asset.original_file_name}><source src={mediaSrc} type={media?.mimeType??'video/mp4'}>Your browser cannot play the compatible video stream.</video>{:else}<V2ImageViewport src={mediaSrc} alt={asset.original_file_name} controller={camera}/>{/if}{/if}</div><aside class="v2-viewer-info">{#if asset}<V2Section title="Details"><V2Card><b>{asset.original_file_name}</b><p class="v2-small v2-muted">{asset.width??'—'} × {asset.height??'—'} · {asset.original_mime_type??'Unknown type'}</p></V2Card></V2Section><V2Section title="Metadata"><V2Card><span class="v2-small">Taken {new Date(asset.taken_at).toLocaleString()}<br>Modified {new Date(asset.file_modified_at).toLocaleString()}<br>{asset.restore_path??'No restore path'}</span></V2Card></V2Section><V2Section title="Restore boundary"><V2Card><span class="v2-small">Restoring this item lets the active data source restore related album, tag and stack state when available.</span></V2Card></V2Section>{:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This item is no longer in trash.</span></V2Card></V2Section>{/if}</aside></div>
  {#snippet footer()}<V2Button disabled={!canPrevious} onclick={previous}>← Previous</V2Button><V2Inline gap="sm"><V2Button variant="primary" disabled={!asset} onclick={restore}>Restore visible</V2Button></V2Inline><V2Button disabled={!canNext} onclick={next}>Next →</V2Button>{/snippet}
</V2ViewerShell>

<style>
  .v2-video-player { width:100%; height:100%; object-fit:contain; background:#000; }
</style>
