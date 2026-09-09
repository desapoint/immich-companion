<script lang="ts">
  import V2AssetRelationModal from './V2AssetRelationModal.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ErrorState from './V2ErrorState.svelte';
  import V2MediaViewport from './V2MediaViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2Section from './V2Section.svelte';
  import V2StackFilmstrip from './V2StackFilmstrip.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { AssetMutationController } from '../state/assetMutations.svelte';
  import { AssetRelationOptionsController } from '../state/assetRelationOptions.svelte';
  import { useOptionalV2Toasts } from '../state/toasts.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { AssetDetailRecord, AssetRecord, AssetSelectionTarget, MediaResource, MutationResult, ViewerNavigationWindow } from '../data/contracts';

  type RelationDialog='album'|'tags'|null;
  type ResultMode='Pagination'|'Infinite';

  let {
    open=false,
    assetId=null,
    assetIds=[],
    resultMode='Pagination',
    collectionPage=1,
    collectionPageSize=24,
    collectionTotal=0,
    startStack=false,
    onclose,
    onnavigate,
    onmutated,
    onfilterrelation,
  }: {
    open?:boolean;
    assetId?:string|null;
    assetIds?:string[];
    resultMode?:ResultMode;
    collectionPage?:number;
    collectionPageSize?:number;
    collectionTotal?:number;
    startStack?:boolean;
    onclose:()=>void;
    onnavigate?:(assetId:string,navigation:ViewerNavigationWindow)=>void|Promise<void>;
    onmutated?:()=>void|Promise<void>;
    onfilterrelation?:(kind:'album'|'tag',id:string)=>void|Promise<void>;
  }=$props();

  const camera=new ViewerViewportController();
  const relations=new AssetRelationOptionsController();
  const toasts=useOptionalV2Toasts();
  const emptyNavigation=():ViewerNavigationWindow=>({previousId:null,nextId:null,position:null,total:0});
  const shortcuts:KeyboardShortcut[]=[
    {keys:'Esc',description:'Close viewer'},
    {keys:'←',description:'Previous asset / stack member'},
    {keys:'→',description:'Next asset / stack member'},
    {keys:'F',description:'Toggle favorite on shown asset'},
    {keys:'A',description:'Toggle archive on shown asset'},
    {keys:['+','='],description:'Zoom in'},
    {keys:'−',description:'Zoom out'},
    {keys:'0',description:'Reset zoom / fit image'},
    {keys:'1',description:'Actual pixel size (1:1)'},
  ];

  let currentId=$state<string|null>(assetId),asset=$state<AssetDetailRecord|undefined>(),media=$state<MediaResource|null>(null),navigation=$state<ViewerNavigationWindow>(emptyNavigation());
  let loading=$state(false),navigationLoading=$state(false),assetError=$state(''),navigationError=$state(''),mediaError=$state(''),mediaRefreshing=$state(false),mediaAttempt=$state(0),loadRequest=0;
  let relationDialog=$state<RelationDialog>(null),relationAlbum=$state(''),relationTags=$state<string[]>([]);
  let sessionInitialized=$state(false),sessionPage=$state(1),sessionPosition=$state<number|null>(null),sessionTotal=$state(0),sessionPages=$state<Record<number,string[]>>({}),sessionInfinite=$state<string[]>([]);

  let stackActive=$state(false),stackLoading=$state(false),stackAutoEntered=$state(false),stackId=$state<string|null>(null),stackPrimaryId=$state<string|null>(null),stackLiveIds=$state<string[]>([]),stackMembers=$state<AssetRecord[]>([]),stackRemovedIds=$state<Set<string>>(new Set()),stackReadyIds=$state<Set<string>>(new Set()),stackDetailCache=$state<Record<string,AssetDetailRecord>>({}),stackMediaCache=$state<Record<string,MediaResource>>({}),stackPendingId=$state<string|null>(null),stackExists=$state(true);
  let stackOriginPage=$state(1),stackOriginPosition=$state<number|null>(null),stackOriginNavigation=$state<ViewerNavigationWindow>(emptyNavigation());

  const mutations=new AssetMutationController(()=>reloadActive(),()=>{});
  const actionBusy=$derived(mutations.busy),actionStatus=$derived(mutations.phase==='applying'?'Applying change…':mutations.phase==='refreshing'?'Refreshing asset…':'');
  const isVideo=$derived(asset?.asset_type==='VIDEO'),needsDecodedImage=$derived(media?.delivery==='decoded'),needsVideoProxy=$derived(media?.delivery==='transcoded');
  const sessionIds=$derived(resultMode==='Pagination'?(sessionPages[sessionPage]??[]):sessionInfinite);
  const sessionIndex=$derived(currentId?sessionIds.indexOf(currentId):-1);
  const stackIndex=$derived(currentId?stackMembers.findIndex((member)=>member.id===currentId):-1);
  const currentMatchesLive=$derived(Boolean(currentId&&assetIds.includes(currentId)&&(resultMode!=='Pagination'||collectionPage===sessionPage)));
  const currentRemovedFromStack=$derived(Boolean(currentId&&stackRemovedIds.has(currentId)));
  const liveStackCount=$derived(stackLiveIds.filter((id)=>!stackRemovedIds.has(id)).length);
  const stackPositionLabel=$derived(stackActive&&stackIndex>=0?`${stackIndex+1} / ${stackMembers.length}`:'');
  const canPrevious=$derived(stackActive?stackIndex>0:Boolean(sessionIndex>0||navigation.previousId));
  const canNext=$derived(stackActive?stackIndex>=0&&stackIndex<stackMembers.length-1:Boolean((sessionIndex>=0&&sessionIndex<sessionIds.length-1)||navigation.nextId));
  const positionLabel=$derived(sessionPosition!==null?`${sessionPosition} / ${sessionTotal||collectionTotal||navigation.total}`:sessionIndex>=0?`Viewer session · ${sessionIndex+1} / ${Math.max(sessionIds.length,1)}`:'—');
  const sizeLabel=$derived(formatFileSize(asset?.file_size_bytes));
  const isStackPrimary=$derived(Boolean(currentId&&stackPrimaryId===currentId));

  function stableMerge(previous:string[],live:string[]):string[]{const seen=new Set(previous);return[...previous,...live.filter((id)=>!seen.has(id))]}
  function detailFromRecord(record:AssetRecord):AssetDetailRecord{return{...record,albums:record.albums??[]}}

  function resetStackSession(){
    stackActive=false;stackLoading=false;stackAutoEntered=false;stackId=null;stackPrimaryId=null;stackLiveIds=[];stackMembers=[];stackRemovedIds=new Set();stackReadyIds=new Set();stackDetailCache={};stackMediaCache={};stackPendingId=null;stackExists=true;
  }

  function initializeInspectionSession(){
    currentId=assetId;sessionPage=collectionPage;sessionTotal=collectionTotal;sessionPosition=currentId?((resultMode==='Pagination'?(collectionPage-1)*collectionPageSize:0)+Math.max(0,assetIds.indexOf(currentId))+1):null;
    sessionPages=resultMode==='Pagination'?{[collectionPage]:[...assetIds]}:{};sessionInfinite=resultMode==='Infinite'?[...assetIds]:[];navigation=emptyNavigation();resetStackSession();
  }

  $effect(()=>{
    if(open&&!sessionInitialized){sessionInitialized=true;initializeInspectionSession()}
    else if(!open&&sessionInitialized){sessionInitialized=false;currentId=assetId;resetStackSession()}
  });

  $effect(()=>{
    if(!open)return;
    const live=[...assetIds];
    sessionTotal=Math.max(sessionTotal,collectionTotal);
    if(resultMode==='Pagination'){
      const existing=sessionPages[collectionPage]??[];
      const merged=stableMerge(existing,live);
      if(merged.length!==existing.length||merged.some((id,index)=>id!==existing[index]))sessionPages={...sessionPages,[collectionPage]:merged};
    }else{
      const merged=stableMerge(sessionInfinite,live);
      if(merged.length!==sessionInfinite.length||merged.some((id,index)=>id!==sessionInfinite[index]))sessionInfinite=merged;
    }
  });

  $effect(()=>{
    const id=currentId;stackActive;
    if(!open)return;
    if(!id){asset=undefined;media=null;navigation=emptyNavigation();return}
    void loadCurrent(id);
  });

  $effect(()=>{if(open&&!isVideo&&!mediaError)requestAnimationFrame(()=>camera.fit())});

  async function loadCurrent(id:string){
    if(stackActive&&stackDetailCache[id]&&stackMediaCache[id]){
      asset=stackDetailCache[id];media=stackMediaCache[id];mediaAttempt+=1;loading=false;navigationLoading=false;assetError='';mediaError='';relationDialog=null;return;
    }
    const request=++loadRequest;loading=true;assetError='';mediaError='';navigationError='';navigationLoading=true;relationDialog=null;
    try{
      const [nextAsset,nextNavigation]=await Promise.all([
        libraryData.assets.details(id),
        libraryData.navigation.asset(id).catch((error)=>{if(request===loadRequest)navigationError=errorMessage(error,'Navigation could not be loaded.');return emptyNavigation()}),
      ]);
      if(request!==loadRequest)return;
      asset=nextAsset;navigation=nextNavigation;media=nextAsset?libraryData.media.view(nextAsset):null;mediaAttempt+=1;
      if(nextNavigation.position!==null){sessionPosition=nextNavigation.position;sessionTotal=Math.max(sessionTotal,nextNavigation.total);sessionPage=resultMode==='Pagination'?Math.max(1,Math.ceil(nextNavigation.position/collectionPageSize)):sessionPage}
      if(nextAsset){
        void onnavigate?.(id,nextNavigation);
        if(startStack&&!stackAutoEntered&&nextAsset.stack){stackAutoEntered=true;void enterStack(nextAsset)}
      }else assetError='This asset is no longer available in the current data source.';
    }catch(error){if(request===loadRequest){asset=undefined;media=null;assetError=errorMessage(error,'The asset could not be loaded.')}}
    finally{if(request===loadRequest){loading=false;navigationLoading=false}}
  }

  async function reloadActive(){
    if(!currentId)return;
    const next=await libraryData.assets.details(currentId);
    if(!next){if(!stackActive)assetError='This asset is no longer available in the current data source.';return}
    asset=next;media=libraryData.media.view(next);mediaAttempt+=1;mediaError='';assetError='';
    if(stackActive&&media){stackDetailCache={...stackDetailCache,[next.id]:next};stackMediaCache={...stackMediaCache,[next.id]:media}}
  }

  function formatFileSize(bytes:number|null|undefined):string{
    if(bytes===null||bytes===undefined)return'Unknown size';
    if(bytes<1024)return`${bytes} B`;
    const units=['KB','MB','GB','TB'];let value=bytes/1024,index=0;
    while(value>=1024&&index<units.length-1){value/=1024;index+=1}
    return`${value.toFixed(value>=10?1:2)} ${units[index]}`;
  }

  async function preloadImage(url:string):Promise<void>{
    if(!url)return;
    const image=new Image();image.decoding='async';image.src=url;
    try{await image.decode()}catch{await new Promise<void>((resolve)=>{image.onload=()=>resolve();image.onerror=()=>resolve()})}
  }

  async function preloadStackMember(member:AssetRecord):Promise<void>{
    const detail=stackDetailCache[member.id]??detailFromRecord(member),resource=stackMediaCache[member.id]??libraryData.media.view(member);
    stackDetailCache={...stackDetailCache,[member.id]:detail};stackMediaCache={...stackMediaCache,[member.id]:resource};
    if(member.asset_type==='VIDEO'){
      if(resource.posterUrl)await preloadImage(resource.posterUrl);
    }else await preloadImage(resource.url);
    stackReadyIds=new Set([...stackReadyIds,member.id]);
    if(stackPendingId===member.id){stackPendingId=null;activateStackMember(member.id)}
  }

  async function ensureStackMembers(ids:string[]):Promise<void>{
    const missing=ids.filter((id)=>!stackMembers.some((member)=>member.id===id));
    if(!missing.length)return;
    const loaded=await libraryData.assets.getMany(missing),map=new Map(loaded.map((member)=>[member.id,member]));
    const allIds=[...new Set([...stackMembers.map((member)=>member.id),...ids])];
    stackMembers=allIds.map((id)=>stackMembers.find((member)=>member.id===id)??map.get(id)).filter((member):member is AssetRecord=>Boolean(member));
    for(const member of loaded)void preloadStackMember(member);
  }

  async function enterStack(source=asset){
    if(!source?.stack||stackLoading)return;
    stackLoading=true;stackActive=true;stackId=source.stack.id;stackPrimaryId=source.stack.primaryAssetId;stackLiveIds=[...new Set(source.stack.assets.length?source.stack.assets:[source.id])];stackRemovedIds=new Set();stackExists=true;
    stackOriginPage=sessionPage;stackOriginPosition=sessionPosition;stackOriginNavigation={...navigation};
    try{
      const loaded=await libraryData.assets.getMany(stackLiveIds),byId=new Map(loaded.map((member)=>[member.id,member]));
      if(!byId.has(source.id))byId.set(source.id,source);
      stackMembers=stackLiveIds.map((id)=>byId.get(id)).filter((member):member is AssetRecord=>Boolean(member));
      if(!stackMembers.some((member)=>member.id===source.id))stackMembers=[source,...stackMembers];
      stackDetailCache={...stackDetailCache,[source.id]:source};
      if(media)stackMediaCache={...stackMediaCache,[source.id]:media};
      stackReadyIds=new Set(media?[source.id]:[]);
      const index=stackMembers.findIndex((member)=>member.id===source.id),priority:AssetRecord[]=[];
      for(const candidate of [source,stackMembers[index-1],stackMembers[index+1],...stackMembers])if(candidate&&!priority.some((member)=>member.id===candidate.id))priority.push(candidate);
      for(const member of priority)void preloadStackMember(member);
    }catch(error){assetError=errorMessage(error,'Stack members could not be loaded.');stackActive=false}
    finally{stackLoading=false}
  }

  function activateStackMember(id:string){
    const detail=stackDetailCache[id],resource=stackMediaCache[id];
    if(!detail||!resource)return;
    currentId=id;asset=detail;media=resource;mediaAttempt+=1;assetError='';mediaError='';loading=false;
  }

  function selectStackMember(id:string){
    if(actionBusy||id===currentId)return;
    const member=stackMembers.find((item)=>item.id===id);if(!member)return;
    if(member.asset_type!=='VIDEO'&&!stackReadyIds.has(id)){stackPendingId=id;void preloadStackMember(member);return}
    activateStackMember(id);
  }

  function exitStack(){
    if(!stackActive)return;
    const id=currentId;stackActive=false;stackPendingId=null;sessionPage=stackOriginPage;sessionPosition=stackOriginPosition;navigation={...stackOriginNavigation};
    if(id){
      if(resultMode==='Pagination'){
        const pageIds=sessionPages[stackOriginPage]??[];
        if(!pageIds.includes(id)){
          const originIndex=Math.max(0,pageIds.indexOf(assetId??''));const next=[...pageIds];next.splice(originIndex+1,0,id);sessionPages={...sessionPages,[stackOriginPage]:next};
        }
      }else if(!sessionInfinite.includes(id)){
        const originIndex=Math.max(0,sessionInfinite.indexOf(assetId??''));const next=[...sessionInfinite];next.splice(originIndex+1,0,id);sessionInfinite=next;
      }
    }
  }

  async function refreshLiveStack(){
    if(!stackId)return;
    const probeId=stackLiveIds.find((id)=>!stackRemovedIds.has(id));
    if(!probeId){stackExists=false;stackLiveIds=[];return}
    const probe=await libraryData.assets.getById(probeId);
    if(!probe?.stack||probe.stack.id!==stackId){stackExists=false;stackLiveIds=[];return}
    stackExists=true;stackPrimaryId=probe.stack.primaryAssetId;stackLiveIds=[...probe.stack.assets];await ensureStackMembers(stackLiveIds);
  }

  function filterRelationship(kind:'album'|'tag',id:string){void onfilterrelation?.(kind,id)}
  function publishMutation(label:string):void{
    if(!toasts)return;
    const retry=mutations.retry;
    const action=retry?{label:'Retry failed',run:async()=>{await retry();publishMutation(label)}}:undefined;
    if(mutations.error){toasts.push({tone:mutations.feedback?'warning':'error',title:mutations.feedback?`${label} needs attention`:`${label} failed`,message:mutations.error,action});return}
    const feedback=mutations.feedback;if(!feedback||feedback.tone==='pending')return;
    toasts.push({tone:feedback.tone==='ok'?'success':feedback.tone==='warn'?'warning':'error',title:feedback.title,message:[feedback.detail,feedback.failures[0]?.reason].filter(Boolean).join(' '),action});
  }

  async function reconcilePage(result:MutationResult|null){if(result?.affectedIds.length)await onmutated?.()}
  function target(id:string):AssetSelectionTarget{return{kind:'ids',ids:[id]}}

  async function runAction(label:string,action:(id:string)=>Promise<MutationResult>){
    if(!asset||actionBusy)return null;
    const id=asset.id,result=await mutations.run(label,()=>action(id),target(id));publishMutation(label);await reconcilePage(result);return result;
  }

  async function favorite(){if(!asset)return;const next=!asset.is_favorite;await runAction(next?'Favorite':'Unfavorite',(id)=>libraryData.assets.setFavorite(target(id),next))}
  async function archive(){if(!asset)return;const next=!asset.is_archived;await runAction(next?'Archive':'Unarchive',(id)=>libraryData.assets.setArchived(target(id),next))}
  async function sync(){await runAction('Sync',(id)=>libraryData.assets.sync(target(id))}
  async function removeTags(){await runAction('Remove tags',(id)=>libraryData.assets.removeTags(target(id))}
  async function removeAlbums(){await runAction('Remove from albums',(id)=>libraryData.assets.removeFromAlbums(target(id))}

  async function removeFromStack(){
    if(!asset)return;const id=asset.id,result=await runAction('Remove this asset from stack',(assetId)=>libraryData.assets.unstack(target(assetId)));
    if(!result?.affectedIds.includes(id))return;
    stackRemovedIds=new Set([...stackRemovedIds,id]);stackLiveIds=stackLiveIds.filter((memberId)=>memberId!==id);await refreshLiveStack();
  }
  async function setStackPrimary(){if(!asset)return;const id=asset.id,result=await runAction('Set stack primary',(assetId)=>libraryData.assets.setStackPrimary(assetId));if(result?.affectedIds.includes(id)){stackPrimaryId=id;await refreshLiveStack()}}
  async function removeCompleteStack(){
    if(!asset)return;const result=await runAction('Remove complete stack',(id)=>libraryData.assets.removeCompleteStack(id));if(!result?.affectedIds.length)return;
    stackRemovedIds=new Set(stackMembers.map((member)=>member.id));stackLiveIds=[];stackExists=false;
  }

  async function moveNormal(delta:-1|1){
    const index=sessionIndex,targetIndex=index+delta;
    if(index>=0&&targetIndex>=0&&targetIndex<sessionIds.length){
      if(resultMode==='Pagination')sessionPosition=(sessionPage-1)*collectionPageSize+targetIndex+1;
      else if(sessionPosition!==null)sessionPosition+=delta;
      currentId=sessionIds[targetIndex];return;
    }
    const id=delta<0?navigation.previousId:navigation.nextId;if(!id)return;
    const expected=navigation.position!==null?navigation.position+delta:sessionPosition!==null?sessionPosition+delta:null;
    if(expected!==null){
      sessionPosition=expected;if(resultMode==='Pagination')sessionPage=Math.max(1,Math.ceil(expected/collectionPageSize));
      try{await onnavigate?.(id,{previousId:null,nextId:null,position:expected,total:navigation.total||sessionTotal})}catch{/* Keep the inspection session usable if collection preloading fails. */}
    }
    currentId=id;
  }
  function previous(){if(stackActive){if(stackIndex>0)selectStackMember(stackMembers[stackIndex-1].id);return}void moveNormal(-1)}
  function next(){if(stackActive){if(stackIndex>=0&&stackIndex<stackMembers.length-1)selectStackMember(stackMembers[stackIndex+1].id);return}void moveNormal(1)}

  async function retryMedia(){if(!asset||mediaRefreshing)return;mediaRefreshing=true;mediaError='';try{media=await libraryData.media.refresh(asset,'view');mediaAttempt+=1;if(stackActive&&currentId&&media)stackMediaCache={...stackMediaCache,[currentId]:media}}catch(error){mediaError=errorMessage(error,'Media could not be refreshed.')}finally{mediaRefreshing=false}}
  function markMediaFailed(){mediaError=asset?.is_offline?'The original source is offline and no usable cached preview is currently available.':'The media resource could not be loaded. It may be unavailable or the access URL may have expired.'}

  async function trash(){
    if(!asset||actionBusy)return;const id=asset.id;
    if(stackActive){
      const index=stackIndex,result=await mutations.run('Move to trash',()=>libraryData.assets.trash(target(id)),target(id),{refresh:async()=>{}});publishMutation('Move to trash');await reconcilePage(result);
      if(result?.affectedIds.includes(id)){
        const remaining=stackMembers.filter((member)=>member.id!==id);stackMembers=remaining;stackLiveIds=stackLiveIds.filter((memberId)=>memberId!==id);stackRemovedIds=new Set([...stackRemovedIds].filter((memberId)=>memberId!==id));delete stackDetailCache[id];delete stackMediaCache[id];
        if(remaining.length){const replacement=remaining[Math.min(index,remaining.length-1)];activateStackMember(replacement.id);await refreshLiveStack()}else onclose();
      }
      return;
    }
    const fallback=sessionIndex>=0?(sessionIds[sessionIndex+1]??sessionIds[sessionIndex-1]??navigation.nextId??navigation.previousId):navigation.nextId??navigation.previousId;
    const result=await mutations.run('Move to trash',()=>libraryData.assets.trash(target(id)),target(id),{refresh:async()=>{},refreshError:'The asset was moved to trash, but the viewer could not move to the next asset.'});publishMutation('Move to trash');await reconcilePage(result);
    if(result?.affectedIds.includes(id)){if(fallback&&await libraryData.assets.getById(fallback))currentId=fallback;else onclose()}
  }

  function selectedOptionValues(kind:'album'|'tag'){return kind==='album'?[relationAlbum].filter(Boolean):[...relationTags]}
  const searchAlbumOptions=(query:string,append=false)=>relations.searchAlbums(query,selectedOptionValues('album'),append);
  const searchTagOptions=(query:string,append=false)=>relations.searchTags(query,selectedOptionValues('tag'),append);
  function openRelationDialog(kind:RelationDialog){if(!kind||!asset||actionBusy)return;relationDialog=kind;relationAlbum='';relationTags=[];mutations.clearError();if(kind==='album')void searchAlbumOptions('');if(kind==='tags')void searchTagOptions('')}
  async function applyRelationDialog(){
    if(!asset||!relationDialog||actionBusy)return;const kind=relationDialog,id=asset.id;let result:MutationResult|null=null;
    if(kind==='album'&&relationAlbum){result=await mutations.run('Add to album',()=>libraryData.assets.addToAlbum(target(id),relationAlbum),target(id));publishMutation('Add to album')}
    if(kind==='tags'&&relationTags.length){result=await mutations.run('Add tags',()=>libraryData.assets.addTags(target(id),relationTags),target(id));publishMutation('Add tags')}
    await reconcilePage(result);if(result)relationDialog=null;
  }
  async function applyCreatedRelation(kind:'album'|'tag',value:string){if(!asset||actionBusy)return;const id=asset.id;let result:MutationResult|null=null;if(kind==='album'){result=await mutations.run('Add to album',()=>libraryData.assets.addToAlbum(target(id),value),target(id));publishMutation('Add to album')}else{result=await mutations.run('Add tags',()=>libraryData.assets.addTags(target(id),[value]),target(id));publishMutation('Add tags')}await reconcilePage(result)}
  function editableTarget(target:EventTarget|null):boolean{return target instanceof Element&&Boolean(target.closest('input,textarea,select,[contenteditable="true"]'))}
  function handleShortcut(event:KeyboardEvent){
    if(!open||event.defaultPrevented||event.ctrlKey||event.metaKey||event.altKey||editableTarget(event.target))return;
    if(event.key==='ArrowLeft'&&canPrevious&&!navigationLoading&&!actionBusy){event.preventDefault();previous();return}
    if(event.key==='ArrowRight'&&canNext&&!navigationLoading&&!actionBusy){event.preventDefault();next();return}
    if((event.key==='f'||event.key==='F')&&asset&&!loading&&!actionBusy){event.preventDefault();void favorite();return}
    if((event.key==='a'||event.key==='A')&&asset&&!loading&&!actionBusy){event.preventDefault();void archive();return}
    if(isVideo)return;
    if(event.key==='+'||event.key==='='){event.preventDefault();camera.setZoom(camera.zoom*1.25);return}
    if(event.key==='-'||event.key==='−'){event.preventDefault();camera.setZoom(camera.zoom/1.25);return}
    if(event.key==='0'){event.preventDefault();camera.fit();return}
    if(event.key==='1'){event.preventDefault();camera.actual()}
  }
</script>

<svelte:window onkeydown={handleShortcut}/>
<V2ViewerShell {open} title="Assets Viewer" {onclose}>
  {#snippet header()}
    <V2Inline gap="sm" wrap>
      <V2Button onclick={onclose}>✕</V2Button><b>Assets Viewer</b><V2Badge text={navigationLoading&&!stackActive?'Locating…':positionLabel}/>
      {#if stackActive}<V2Badge text={`Stack · ${stackPositionLabel}`}/>{/if}
      {#if !currentMatchesLive}<V2Badge tone="warn" text="No longer matches current search"/>{/if}
      {#if currentRemovedFromStack}<V2Badge tone="warn" text="Removed from stack"/>{/if}
      {#if actionStatus}<V2Badge text={actionStatus}/>{/if}{#if asset?.is_offline}<V2Badge text="Source offline"/>{/if}{#if needsVideoProxy}<V2Badge text="Transcoded playback"/>{:else if needsDecodedImage}<V2Badge text="Decoded preview"/>{/if}
    </V2Inline>
    <V2Inline gap="sm">{#if !isVideo}<V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Reset zoom and fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></V2Inline>
  {/snippet}

  <div class="v2-viewer-workarea">
    <div class="v2-viewer-stage">
      <div class="v2-image-stage">{#if loading}<span class="v2-muted">Loading asset…</span>{:else if assetError}<V2ErrorState title="Asset unavailable" message={assetError} onretry={()=>currentId&&void loadCurrent(currentId)}/>{:else if mediaError}<V2ErrorState title={asset?.is_offline?'Source offline':'Media unavailable'} message={mediaError} retryLabel={mediaRefreshing?'Refreshing…':'Retry media'} onretry={()=>void retryMedia()}/>{:else if asset&&media}{#key mediaAttempt}<V2MediaViewport resource={media} assetType={asset.asset_type} alt={asset.original_file_name} controller={camera} onerror={markMediaFailed}/>{/key}{/if}</div>
      <aside class="v2-viewer-info">
        {#if navigationError&&!stackActive}<V2Section title="Navigation"><V2Card><span class="v2-small v2-muted">{navigationError} Session navigation remains available when possible.</span></V2Card></V2Section>{/if}
        {#if asset}
          <V2Section title="Details"><V2Card><b>{asset.original_file_name}</b><p class="v2-small v2-muted">{asset.width??'—'} × {asset.height??'—'} · {asset.original_mime_type??'Unknown type'} · {sizeLabel}</p>{#if asset.is_offline}<p class="v2-small v2-muted">The original source is currently offline. A cached or generated derivative may still be viewable.</p>{/if}{#if needsVideoProxy}<p class="v2-small v2-muted">Original format is preserved in metadata; playback uses a browser-compatible derivative.</p>{:else if needsDecodedImage}<p class="v2-small v2-muted">Original format is preserved; viewing uses a decoded browser-compatible derivative.</p>{/if}</V2Card></V2Section>
          <V2Section title="Metadata"><V2Card><dl class="viewer-facts"><div><dt>Taken</dt><dd>{new Date(asset.file_created_at).toLocaleString()}</dd></div><div><dt>Source</dt><dd>{asset.library_id?`External library · ${asset.library_id}`:'Immich upload'}</dd></div><div><dt>File size</dt><dd>{sizeLabel}</dd></div></dl></V2Card></V2Section>
          <V2Section title="Relationships"><V2Card><div class="viewer-relations">
            <div class="viewer-relation"><b>Albums</b><div class="viewer-pills">{#each asset.albums as album (album.id)}<V2Badge text={album.name} title={`Search assets in ${album.name}`} onclick={()=>filterRelationship('album',album.id)}/>{:else}<span class="v2-small v2-muted">No albums</span>{/each}</div></div>
            <div class="viewer-relation"><b>Tags</b><div class="viewer-pills">{#each asset.tags as tag (tag.id)}<V2Badge text={tag.name} title={`Search assets tagged ${tag.name}`} onclick={()=>filterRelationship('tag',tag.id)}/>{:else}<span class="v2-small v2-muted">No tags</span>{/each}</div></div>
            <div class="viewer-status-grid"><div><b>Favorite</b><span class="v2-small">{asset.is_favorite?'Yes':'No'}</span></div><div><b>Archived</b><span class="v2-small">{asset.is_archived?'Yes':'No'}</span></div></div>
            {#if stackActive}
              <div class="viewer-relation"><b>Stack</b><span class="v2-small">{stackExists?`${liveStackCount} live member${liveStackCount===1?'':'s'}`:'Stack no longer exists'} · viewing {stackMembers.length}{currentRemovedFromStack?' · this asset was removed':''}</span></div>
            {:else if asset.stack}
              <div class="viewer-relation"><b>Stack</b><span class="v2-small">{asset.stack.assetCount} assets · {asset.stack.primaryAssetId===asset.id?'Primary asset':'Stack member'}</span><V2Inline gap="sm" wrap><V2Button onclick={()=>void enterStack(asset)}>View stack</V2Button>{#if asset.stack.primaryAssetId!==asset.id}<V2Button onclick={()=>void setStackPrimary()}>Set as primary</V2Button>{/if}<V2Button onclick={()=>void removeFromStack()}>Remove this asset</V2Button><V2Button variant="danger" onclick={()=>void removeCompleteStack()}>Remove complete stack</V2Button></V2Inline></div>
            {/if}
          </div></V2Card></V2Section>
        {:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This asset is no longer available in the current data source.</span></V2Card></V2Section>{/if}
      </aside>
    </div>

    {#if stackActive}
      <div class="v2-stack-inspection-bar">
        <div class="v2-stack-inspection-head">
          <V2Inline gap="sm" wrap><b>Stack inspection</b><V2Badge text={stackExists?`${liveStackCount} live member${liveStackCount===1?'':'s'}`:'Stack no longer exists'}/>{#if stackMembers.length!==liveStackCount}<V2Badge text={`Viewing ${stackMembers.length}`}/>{/if}{#if stackLoading}<V2Badge text="Loading stack…"/>{/if}{#if stackPendingId}<V2Badge text="Preparing member…"/>{/if}</V2Inline>
          <V2Inline gap="sm" wrap>{#if stackExists&&!currentRemovedFromStack&&!isStackPrimary}<V2Button disabled={actionBusy} onclick={()=>void setStackPrimary()}>Set as primary</V2Button>{/if}{#if stackExists&&!currentRemovedFromStack}<V2Button disabled={actionBusy} onclick={()=>void removeFromStack()}>Remove this asset</V2Button>{/if}{#if stackExists}<V2Button variant="danger" disabled={actionBusy} onclick={()=>void removeCompleteStack()}>Remove complete stack</V2Button>{/if}<V2Button onclick={exitStack}>Exit stack</V2Button></V2Inline>
        </div>
        {#if !stackExists}<span class="v2-small v2-muted">The live stack no longer exists. Its assets stay available in this inspection session until you exit stack view.</span>{/if}
        <V2StackFilmstrip members={stackMembers} {currentId} primaryId={stackPrimaryId} removedIds={stackRemovedIds} readyIds={stackReadyIds} disabled={actionBusy} onselect={selectStackMember}/>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <V2Button disabled={!canPrevious||navigationLoading||actionBusy} onclick={previous}>← Previous</V2Button>
    <V2Inline gap="sm" wrap={true}><V2Button disabled={!asset||loading||actionBusy} onclick={favorite}>{asset?.is_favorite?'Unfavorite':'Favorite'}</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={archive}>{asset?.is_archived?'Unarchive':'Archive'}</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={()=>openRelationDialog('album')}>Album</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={()=>openRelationDialog('tags')}>Tags</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={sync}>Sync</V2Button>{#if asset?.tags.length}<V2Button disabled={actionBusy} onclick={removeTags}>Remove tags</V2Button>{/if}<V2Button disabled={!asset||loading||actionBusy} onclick={removeAlbums}>Remove from albums</V2Button><V2Button variant="danger" disabled={!asset||loading||actionBusy} onclick={trash}>Trash</V2Button></V2Inline>
    <V2Button disabled={!canNext||navigationLoading||actionBusy} onclick={next}>Next →</V2Button>
  {/snippet}
</V2ViewerShell>

{#if relationDialog}
  <V2AssetRelationModal
    kind={relationDialog}
    selectedCount={1}
    albumValue={relationAlbum}
    tagValues={relationTags}
    albumOptions={relations.albumOptions}
    tagOptions={relations.tagOptions}
    albumLoading={relations.albumLoading}
    tagLoading={relations.tagLoading}
    albumHasMore={Boolean(relations.albumCursor)}
    tagHasMore={Boolean(relations.tagCursor)}
    busy={actionBusy}
    onalbumchange={(value)=>relationAlbum=value}
    ontagschange={(values)=>relationTags=values}
    onalbumsearch={(value)=>void searchAlbumOptions(value)}
    ontagsearch={(value)=>void searchTagOptions(value)}
    onalbumloadmore={()=>void searchAlbumOptions(relations.albumQuery,true)}
    ontagloadmore={()=>void searchTagOptions(relations.tagQuery,true)}
    oncreatealbum={(input)=>relations.createAlbum(input)}
    oncreatetag={(input)=>relations.createTag(input)}
    oncreated={async(kind,option)=>applyCreatedRelation(kind,option.value)}
    onclose={()=>{if(!actionBusy)relationDialog=null}}
    onapply={()=>void applyRelationDialog()}
  />
{/if}

<style>
  .v2-viewer-workarea{min-height:0;display:grid;grid-template-rows:minmax(0,1fr) auto}.v2-stack-inspection-bar{display:grid;gap:8px;padding:9px 12px 7px;border-top:1px solid var(--v2-line);background:#0d131b;min-width:0}.v2-stack-inspection-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
  .viewer-facts{display:grid;gap:.5rem;margin:0}.viewer-facts div{display:grid;grid-template-columns:4.5rem minmax(0,1fr);gap:.65rem}.viewer-facts dt,.viewer-relation>b,.viewer-status-grid b{color:var(--v2-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}.viewer-facts dd{margin:0;font-size:.75rem;overflow-wrap:anywhere}.viewer-relations{display:grid;gap:.85rem}.viewer-relation{display:grid;gap:.4rem}.viewer-pills{display:flex;flex-wrap:wrap;gap:.35rem}.viewer-pills :global(.v2-badge){font-size:8px}.viewer-status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.viewer-status-grid div{display:grid;gap:.25rem}
</style>
