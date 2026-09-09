<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ErrorState from './V2ErrorState.svelte';
  import V2MediaViewport from './V2MediaViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ViewerAssetFacts from './V2ViewerAssetFacts.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { MediaResource, TrashAssetRecord, ViewerNavigationWindow } from '../data/contracts';

  let { open=false, assetId=null, assetIds=[], restoreBusy=false, onclose, onnavigate, onrestore }: { open?:boolean; assetId?:string|null; assetIds?:string[]; restoreBusy?:boolean; onclose:()=>void; onnavigate?:(assetId:string,navigation:ViewerNavigationWindow)=>void|Promise<void>; onrestore?:(assetId:string)=>boolean|Promise<boolean> }=$props();
  const camera=new ViewerViewportController();
  const emptyNavigation=():ViewerNavigationWindow=>({previousId:null,nextId:null,position:null,total:0});
  const shortcuts:KeyboardShortcut[]=[
    {keys:'Esc',description:'Close viewer'},
    {keys:'←',description:'Previous trash asset'},
    {keys:'→',description:'Next trash asset'},
    {keys:['+','='],description:'Zoom in'},
    {keys:'−',description:'Zoom out'},
    {keys:'0',description:'Reset zoom / fit image'},
    {keys:'1',description:'Actual pixel size (1:1)'},
  ];
  let currentId=$derived<string|null>(assetId),asset=$state<TrashAssetRecord|undefined>(),media=$state<MediaResource|null>(null),navigation=$state<ViewerNavigationWindow>(emptyNavigation());
  let loading=$state(false),navigationLoading=$state(false),assetError=$state(''),navigationError=$state(''),mediaError=$state(''),mediaRefreshing=$state(false),mediaAttempt=$state(0),loadRequest=0;
  $effect(()=>{const id=currentId;if(!id){asset=undefined;media=null;navigation=emptyNavigation();return}void loadCurrent(id)});
  const fallbackIndex=$derived(currentId?assetIds.indexOf(currentId):-1),isVideo=$derived(asset?.type==='VIDEO');
  const canPrevious=$derived(Boolean(navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null))),canNext=$derived(Boolean(navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null)));
  const positionLabel=$derived(navigation.position!==null?`${navigation.position} / ${navigation.total}`:fallbackIndex>=0?`${fallbackIndex+1} / ${assetIds.length}`:'—');
  $effect(()=>{if(open&&!isVideo&&!mediaError)requestAnimationFrame(()=>camera.fit())});

  async function loadCurrent(id:string){
    const request=++loadRequest;loading=true;assetError='';mediaError='';navigationError='';navigationLoading=true;
    try{
      const [nextAsset,nextNavigation]=await Promise.all([
        libraryData.assets.getTrashById(id),
        libraryData.navigation.trash(id).catch((error)=>{if(request===loadRequest)navigationError=errorMessage(error,'Navigation could not be loaded.');return emptyNavigation()}),
      ]);
      if(request!==loadRequest)return;
      asset=nextAsset;
      navigation=nextNavigation;
      media=nextAsset?libraryData.media.view(nextAsset):null;
      mediaAttempt+=1;
      if(nextAsset)void onnavigate?.(id,nextNavigation);
      else assetError='This item is no longer in trash.';
    }catch(error){if(request===loadRequest){asset=undefined;media=null;assetError=errorMessage(error,'The trash asset could not be loaded.')}}
    finally{if(request===loadRequest){loading=false;navigationLoading=false}}
  }
  async function moveTo(id:string,delta:-1|1){
    if(navigation.position!==null){
      try{await onnavigate?.(id,{previousId:null,nextId:null,position:navigation.position+delta,total:navigation.total})}catch{/* Viewer navigation remains available even if the backing collection cannot preload. */}
    }
    currentId=id;
  }
  function previous(){const id=navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null);if(id)void moveTo(id,-1)}
  function next(){const id=navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null);if(id)void moveTo(id,1)}
  async function retryMedia(){if(!asset||mediaRefreshing)return;mediaRefreshing=true;mediaError='';try{media=await libraryData.media.refresh(asset,'view');mediaAttempt+=1}catch(error){mediaError=errorMessage(error,'Media could not be refreshed.')}finally{mediaRefreshing=false}}
  function markMediaFailed(){mediaError='The media resource could not be loaded. It may be unavailable or the access URL may have expired.'}
  async function restore(){
    if(!asset||restoreBusy)return;
    const restoringId=asset.id;
    const fallback=navigation.nextId??navigation.previousId??(fallbackIndex>=0?(assetIds[fallbackIndex+1]??assetIds[fallbackIndex-1]??null):null);
    const restored=onrestore?await onrestore(restoringId):(await libraryData.assets.restore({kind:'ids',ids:[restoringId]})).failed.every((failure)=>failure.id!==restoringId);
    if(!restored)return;
    if(fallback&&await libraryData.assets.getTrashById(fallback))currentId=fallback;else onclose();
  }
  function editableTarget(target:EventTarget|null):boolean{return target instanceof Element&&Boolean(target.closest('input,textarea,select,[contenteditable="true"]'))}
  function handleShortcut(event:KeyboardEvent){
    if(!open||event.defaultPrevented||event.ctrlKey||event.metaKey||event.altKey||editableTarget(event.target))return;
    if(event.key==='ArrowLeft'&&canPrevious&&!navigationLoading){event.preventDefault();previous();return}
    if(event.key==='ArrowRight'&&canNext&&!navigationLoading){event.preventDefault();next();return}
    if(isVideo)return;
    if(event.key==='+'||event.key==='='){event.preventDefault();camera.setZoom(camera.zoom*1.25);return}
    if(event.key==='-'||event.key==='−'){event.preventDefault();camera.setZoom(camera.zoom/1.25);return}
    if(event.key==='0'){event.preventDefault();camera.fit();return}
    if(event.key==='1'){event.preventDefault();camera.actual()}
  }
</script>
<svelte:window onkeydown={handleShortcut}/>
<V2ViewerShell {open} title="Restore Viewer" {onclose}>
  {#snippet header()}<V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Restore Viewer</b><V2Badge text={navigationLoading?'Locating…':positionLabel}/>{#if media?.delivery==='transcoded'}<V2Badge text="Transcoded playback"/>{:else if media?.delivery==='decoded'}<V2Badge text="Decoded preview"/>{/if}</V2Inline><V2Inline gap="sm">{#if !isVideo}<V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Reset zoom and fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></V2Inline>{/snippet}
  <div class="v2-viewer-stage"><div class="v2-image-stage">{#if loading}<span class="v2-muted">Loading trash asset…</span>{:else if assetError}<V2ErrorState title="Asset unavailable" message={assetError} onretry={()=>currentId&&void loadCurrent(currentId)}/>{:else if mediaError}<V2ErrorState title="Media unavailable" message={mediaError} retryLabel={mediaRefreshing?'Refreshing…':'Retry media'} onretry={()=>void retryMedia()}/>{:else if asset&&media}{#key mediaAttempt}<V2MediaViewport resource={media} assetType={asset.type} alt={asset.original_file_name} controller={camera} onerror={markMediaFailed}/>{/key}{/if}</div><aside class="v2-viewer-info">{#if navigationError}<V2Section title="Navigation"><V2Card><span class="v2-small v2-muted">{navigationError} Loaded-page navigation remains available when possible.</span></V2Card></V2Section>{/if}{#if asset}<V2ViewerAssetFacts filename={asset.original_file_name} width={asset.width} height={asset.height} mimeType={asset.original_mime_type} fileSizeBytes={asset.file_size_bytes} path={asset.restore_path} offline={asset.is_offline} takenAt={asset.taken_at} libraryId={asset.library_id} delivery={media?.delivery}/><V2Section title="Restore boundary"><V2Card><span class="v2-small">Associations are intentionally omitted while this asset is in Immich trash. Restoring it refreshes its normal workspace data.</span></V2Card></V2Section>{:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This item is no longer in trash.</span></V2Card></V2Section>{/if}</aside></div>
  {#snippet footer()}<V2Button disabled={!canPrevious||navigationLoading||restoreBusy} onclick={previous}>← Previous</V2Button><V2Inline gap="sm"><V2Button variant="primary" disabled={!asset||loading||restoreBusy} onclick={restore}>{restoreBusy?'Restoring…':'Restore visible'}</V2Button></V2Inline><V2Button disabled={!canNext||navigationLoading||restoreBusy} onclick={next}>Next →</V2Button>{/snippet}
</V2ViewerShell>
