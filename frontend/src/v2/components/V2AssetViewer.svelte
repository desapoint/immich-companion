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
  import type { AssetRecord } from '../data/contracts';

  let { open=false, assetId=null, assetIds=[], onclose }: { open?:boolean; assetId?:string|null; assetIds?:string[]; onclose:()=>void }=$props();
  const camera=new ViewerViewportController();
  let currentId=$state<string|null>(assetId),asset=$state<AssetRecord|undefined>();
  $effect(()=>{if(assetId!==null)currentId=assetId});
  $effect(()=>{const id=currentId;if(!id){asset=undefined;return}void(async()=>asset=await libraryData.assets.getById(id))()});
  const currentIndex=$derived(currentId?assetIds.indexOf(currentId):-1),imageSrc=$derived(asset?libraryData.media.fullSize(asset):''),canPrevious=$derived(currentIndex>0),canNext=$derived(currentIndex>=0&&currentIndex<assetIds.length-1),positionLabel=$derived(currentIndex>=0?`${currentIndex+1} / ${assetIds.length}`:'—'),sizeLabel=$derived(asset?.file_size_bytes?`${(asset.file_size_bytes/1_048_576).toFixed(1)} MB`:'Unknown size');
  $effect(()=>{if(open)requestAnimationFrame(()=>camera.fit())});
  function previous(){if(canPrevious)currentId=assetIds[currentIndex-1]}
  function next(){if(canNext)currentId=assetIds[currentIndex+1]}
  async function reload(){asset=currentId?await libraryData.assets.getById(currentId):undefined}
  async function favorite(){if(!asset)return;await libraryData.assets.setFavorite([asset.id],!asset.is_favorite);await reload()}
  async function archive(){if(!asset)return;await libraryData.assets.setArchived([asset.id],!asset.is_archived);await reload()}
  async function trash(){if(!asset)return;const fallback=assetIds[currentIndex+1]??assetIds[currentIndex-1]??null;await libraryData.assets.trash([asset.id]);if(fallback&&await libraryData.assets.getById(fallback))currentId=fallback;else onclose()}
</script>
<V2ViewerShell {open} title="Assets Viewer" {onclose}>
  {#snippet header()}<V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Assets Viewer</b><V2Badge text={positionLabel}/></V2Inline><V2Inline gap="sm"><V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button></V2Inline>{/snippet}
  <div class="v2-viewer-stage"><div class="v2-image-stage">{#if asset}<V2ImageViewport src={imageSrc} alt={asset.original_file_name} controller={camera}/>{/if}</div><aside class="v2-viewer-info">{#if asset}<V2Section title="Details"><V2Card><b>{asset.original_file_name}</b><p class="v2-small v2-muted">{asset.width??'—'} × {asset.height??'—'} · {asset.original_mime_type??'Unknown type'} · {sizeLabel}</p></V2Card></V2Section><V2Section title="Metadata"><V2Card><span class="v2-small">Taken {new Date(asset.file_created_at).toLocaleString()}<br>{asset.library_id?'External library':'Default library'}<br>{asset.tags.length} tag{asset.tags.length===1?'':'s'}{asset.stack?` · stack of ${asset.stack.assetCount}`:''}</span></V2Card></V2Section><V2Section title="Relationships"><V2Card><span class="v2-small">{asset.tags.length?asset.tags.map((tag)=>tag.name).join(' · '):'No tags'}<br>{asset.is_favorite?'Favorite':'Not favorite'} · {asset.is_archived?'Archived':'Not archived'}</span></V2Card></V2Section>{:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This asset is no longer available in the current data source.</span></V2Card></V2Section>{/if}</aside></div>
  {#snippet footer()}<V2Button disabled={!canPrevious} onclick={previous}>← Previous</V2Button><V2Inline gap="sm"><V2Button disabled={!asset} onclick={favorite}>{asset?.is_favorite?'Unfavorite':'Favorite'}</V2Button><V2Button disabled={!asset} onclick={archive}>{asset?.is_archived?'Unarchive':'Archive'}</V2Button><V2Button variant="danger" disabled={!asset} onclick={trash}>Trash</V2Button></V2Inline><V2Button disabled={!canNext} onclick={next}>Next →</V2Button>{/snippet}
</V2ViewerShell>
