<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ErrorState from './V2ErrorState.svelte';
  import V2ImageViewport from './V2ImageViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { AssetRecord, AssetSelectionTarget, MediaResource, ViewerNavigationWindow } from '../data/contracts';

  let { open=false, assetId=null, assetIds=[], onclose }: { open?:boolean; assetId?:string|null; assetIds?:string[]; onclose:()=>void }=$props();
  const camera=new ViewerViewportController();
  const emptyNavigation=():ViewerNavigationWindow=>({previousId:null,nextId:null,position:null,total:0});
  const shortcuts:KeyboardShortcut[]=[
    {keys:'Esc',description:'Close viewer'},
    {keys:'←',description:'Previous asset'},
    {keys:'→',description:'Next asset'},
    {keys:'F',description:'Toggle favorite'},
    {keys:'A',description:'Toggle archive'},
    {keys:['+','='],description:'Zoom in'},
    {keys:'−',description:'Zoom out'},
    {keys:'0',description:'Reset zoom / fit image'},
    {keys:'1',description:'Actual pixel size (1:1)'},
  ];
  let currentId=$state<string|null>(assetId),asset=$state<AssetRecord|undefined>(),media=$state<MediaResource|null>(null),navigation=$state<ViewerNavigationWindow>(emptyNavigation());
  let loading=$state(false),navigationLoading=$state(false),assetError=$state(''),navigationError=$state(''),mediaError=$state(''),mediaRefreshing=$state(false),mediaAttempt=$state(0),loadRequest=0;
  $effect(()=>{if(assetId!==null)currentId=assetId});
  $effect(()=>{const id=currentId;if(!id){asset=undefined;media=null;navigation=emptyNavigation();return}void loadCurrent(id)});

  const fallbackIndex=$derived(currentId?assetIds.indexOf(currentId):-1),mediaSrc=$derived(media?.url??''),posterSrc=$derived(media?.posterUrl??(asset?libraryData.media.thumbnail(asset).url:'')),isVideo=$derived(asset?.asset_type==='VIDEO'),needsDecodedImage=$derived(media?.delivery==='decoded'),needsVideoProxy=$derived(media?.delivery==='transcoded');
  const canPrevious=$derived(Boolean(navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null))),canNext=$derived(Boolean(navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null)));
  const positionLabel=$derived(navigation.position!==null?`${navigation.position} / ${navigation.total}`:fallbackIndex>=0?`${fallbackIndex+1} / ${assetIds.length}`:'—'),sizeLabel=$derived(asset?.file_size_bytes?`${(asset.file_size_bytes/1_048_576).toFixed(1)} MB`:'Unknown size');
  $effect(()=>{if(open&&!isVideo&&!mediaError)requestAnimationFrame(()=>camera.fit())});

  async function loadCurrent(id:string){
    const request=++loadRequest;loading=true;assetError='';mediaError='';navigationError='';navigationLoading=true;
    try{
      const [nextAsset,nextNavigation]=await Promise.all([
        libraryData.assets.getById(id),
        libraryData.navigation.asset(id).catch((error)=>{if(request===loadRequest)navigationError=errorMessage(error,'Navigation could not be loaded.');return emptyNavigation()}),
      ]);
      if(request!==loadRequest)return;
      asset=nextAsset;
      navigation=nextNavigation;
      media=nextAsset?libraryData.media.view(nextAsset):null;
      mediaAttempt+=1;
      if(!nextAsset)assetError='This asset is no longer available in the current data source.';
    }catch(error){if(request===loadRequest){asset=undefined;media=null;assetError=errorMessage(error,'The asset could not be loaded.')}}
    finally{if(request===loadRequest){loading=false;navigationLoading=false}}
  }
  function previous(){const id=navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null);if(id)currentId=id}
  function next(){const id=navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null);if(id)currentId=id}
  function target(id:string):AssetSelectionTarget{return{kind:'ids',ids:[id]}}
  async function reload(){if(currentId)await loadCurrent(currentId)}
  async function retryMedia(){if(!asset||mediaRefreshing)return;mediaRefreshing=true;mediaError='';try{media=await libraryData.media.refresh(asset,'view');mediaAttempt+=1}catch(error){mediaError=errorMessage(error,'Media could not be refreshed.')}finally{mediaRefreshing=false}}
  function markMediaFailed(){mediaError=asset?.is_offline?'The original source is offline and no usable cached preview is currently available.':'The media resource could not be loaded. It may be unavailable or the access URL may have expired.'}
  async function favorite(){if(!asset)return;await libraryData.assets.setFavorite(target(asset.id),!asset.is_favorite);await reload()}
  async function archive(){if(!asset)return;await libraryData.assets.setArchived(target(asset.id),!asset.is_archived);await reload()}
  async function trash(){if(!asset)return;const fallback=navigation.nextId??navigation.previousId??(fallbackIndex>=0?(assetIds[fallbackIndex+1]??assetIds[fallbackIndex-1]??null):null);await libraryData.assets.trash(target(asset.id));if(fallback&&await libraryData.assets.getById(fallback))currentId=fallback;else onclose()}
  function editableTarget(target:EventTarget|null):boolean{return target instanceof Element&&Boolean(target.closest('input,textarea,select,[contenteditable="true"]'))}
  function handleShortcut(event:KeyboardEvent){
    if(!open||event.defaultPrevented||event.ctrlKey||event.metaKey||event.altKey||editableTarget(event.target))return;
    if(event.key==='ArrowLeft'&&canPrevious&&!navigationLoading){event.preventDefault();previous();return}
    if(event.key==='ArrowRight'&&canNext&&!navigationLoading){event.preventDefault();next();return}
    if((event.key==='f'||event.key==='F')&&asset&&!loading){event.preventDefault();void favorite();return}
    if((event.key==='a'||event.key==='A')&&asset&&!loading){event.preventDefault();void archive();return}
    if(isVideo)return;
    if(event.key==='+'||event.key==='='){event.preventDefault();camera.setZoom(camera.zoom*1.25);return}
    if(event.key==='-'||event.key==='−'){event.preventDefault();camera.setZoom(camera.zoom/1.25);return}
    if(event.key==='0'){event.preventDefault();camera.fit();return}
    if(event.key==='1'){event.preventDefault();camera.actual()}
  }
</script>
<svelte:window onkeydown={handleShortcut}/>
<V2ViewerShell {open} title="Assets Viewer" {onclose}>
  {#snippet header()}<V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Assets Viewer</b><V2Badge text={navigationLoading?'Locating…':positionLabel}/>{#if asset?.is_offline}<V2Badge text="Source offline"/>{/if}{#if needsVideoProxy}<V2Badge text="Transcoded playback"/>{:else if needsDecodedImage}<V2Badge text="Decoded preview"/>{/if}</V2Inline><V2Inline gap="sm">{#if !isVideo}<V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Reset zoom and fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></V2Inline>{/snippet}
  <div class="v2-viewer-stage"><div class="v2-image-stage">{#if loading}<span class="v2-muted">Loading asset…</span>{:else if assetError}<V2ErrorState title="Asset unavailable" message={assetError} onretry={()=>currentId&&void loadCurrent(currentId)}/>{:else if mediaError}<V2ErrorState title={asset?.is_offline?'Source offline':'Media unavailable'} message={mediaError} retryLabel={mediaRefreshing?'Refreshing…':'Retry media'} onretry={()=>void retryMedia()}/>{:else if asset}{#key mediaAttempt}{#if isVideo}<video class="v2-video-player" controls playsinline preload="metadata" poster={posterSrc} aria-label={asset.original_file_name} onerror={markMediaFailed}><source src={mediaSrc} type={media?.mimeType??'video/mp4'}>Your browser cannot play the compatible video stream.</video>{:else}<V2ImageViewport src={mediaSrc} alt={asset.original_file_name} controller={camera} onerror={markMediaFailed}/>{/if}{/key}{/if}</div><aside class="v2-viewer-info">{#if navigationError}<V2Section title="Navigation"><V2Card><span class="v2-small v2-muted">{navigationError} Loaded-page navigation remains available when possible.</span></V2Card></V2Section>{/if}{#if asset}<V2Section title="Details"><V2Card><b>{asset.original_file_name}</b><p class="v2-small v2-muted">{asset.width??'—'} × {asset.height??'—'} · {asset.original_mime_type??'Unknown type'} · {sizeLabel}</p>{#if asset.is_offline}<p class="v2-small v2-muted">The original source is currently offline. A cached or generated derivative may still be viewable.</p>{/if}{#if needsVideoProxy}<p class="v2-small v2-muted">Original format is preserved in metadata; playback uses a browser-compatible derivative.</p>{:else if needsDecodedImage}<p class="v2-small v2-muted">Original format is preserved; viewing uses a decoded browser-compatible derivative.</p>{/if}</V2Card></V2Section><V2Section title="Metadata"><V2Card><span class="v2-small">Taken {new Date(asset.file_created_at).toLocaleString()}<br>{asset.library_id?'External library':'Default library'}<br>{asset.tags.length} tag{asset.tags.length===1?'':'s'}{asset.stack?` · stack of ${asset.stack.assetCount}`:''}</span></V2Card></V2Section><V2Section title="Relationships"><V2Card><span class="v2-small">{asset.tags.length?asset.tags.map((tag)=>tag.name).join(' · '):'No tags'}<br>{asset.is_favorite?'Favorite':'Not favorite'} · {asset.is_archived?'Archived':'Not archived'}</span></V2Card></V2Section>{:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This asset is no longer available in the current data source.</span></V2Card></V2Section>{/if}</aside></div>
  {#snippet footer()}<V2Button disabled={!canPrevious||navigationLoading} onclick={previous}>← Previous</V2Button><V2Inline gap="sm"><V2Button disabled={!asset||loading} onclick={favorite}>{asset?.is_favorite?'Unfavorite':'Favorite'}</V2Button><V2Button disabled={!asset||loading} onclick={archive}>{asset?.is_archived?'Unarchive':'Archive'}</V2Button><V2Button variant="danger" disabled={!asset||loading} onclick={trash}>Trash</V2Button></V2Inline><V2Button disabled={!canNext||navigationLoading} onclick={next}>Next →</V2Button>{/snippet}
</V2ViewerShell>

<style>
  .v2-video-player { width:100%; height:100%; object-fit:contain; background:#000; }
</style>
