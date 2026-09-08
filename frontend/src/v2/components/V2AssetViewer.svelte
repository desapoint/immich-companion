<script lang="ts">
  import V2AssetRelationModal from './V2AssetRelationModal.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ErrorState from './V2ErrorState.svelte';
  import V2MediaViewport from './V2MediaViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2OperationFeedback from './V2OperationFeedback.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { AssetMutationController } from '../state/assetMutations.svelte';
  import { AssetRelationOptionsController } from '../state/assetRelationOptions.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { AssetRecord, AssetSelectionTarget, MediaResource, MutationResult, ViewerNavigationWindow } from '../data/contracts';

  type RelationDialog='album'|'tags'|null;

  let { open=false, assetId=null, assetIds=[], onclose }: { open?:boolean; assetId?:string|null; assetIds?:string[]; onclose:()=>void }=$props();
  const camera=new ViewerViewportController();
  const relations=new AssetRelationOptionsController();
  const mutations=new AssetMutationController(()=>reload(),()=>{});
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
  let currentId=$derived<string|null>(assetId),asset=$state<AssetRecord|undefined>(),media=$state<MediaResource|null>(null),navigation=$state<ViewerNavigationWindow>(emptyNavigation());
  let loading=$state(false),navigationLoading=$state(false),assetError=$state(''),navigationError=$state(''),mediaError=$state(''),mediaRefreshing=$state(false),mediaAttempt=$state(0),loadRequest=0;
  let relationDialog=$state<RelationDialog>(null),relationAlbum=$state(''),relationTags=$state<string[]>([]);
  const actionBusy=$derived(mutations.busy),actionError=$derived(mutations.error),actionStatus=$derived(mutations.phase==='applying'?'Applying change…':mutations.phase==='refreshing'?'Refreshing asset…':'');
  $effect(()=>{const id=currentId;if(!id){asset=undefined;media=null;navigation=emptyNavigation();return}void loadCurrent(id)});

  const fallbackIndex=$derived(currentId?assetIds.indexOf(currentId):-1),isVideo=$derived(asset?.asset_type==='VIDEO'),needsDecodedImage=$derived(media?.delivery==='decoded'),needsVideoProxy=$derived(media?.delivery==='transcoded');
  const canPrevious=$derived(Boolean(navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null))),canNext=$derived(Boolean(navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null)));
  const positionLabel=$derived(navigation.position!==null?`${navigation.position} / ${navigation.total}`:fallbackIndex>=0?`${fallbackIndex+1} / ${assetIds.length}`:'—'),sizeLabel=$derived(asset?.file_size_bytes?`${(asset.file_size_bytes/1_048_576).toFixed(1)} MB`:'Unknown size');
  const isStackPrimary=$derived(Boolean(asset?.stack&&asset.stack.primaryAssetId===asset.id));
  $effect(()=>{if(open&&!isVideo&&!mediaError)requestAnimationFrame(()=>camera.fit())});

  async function loadCurrent(id:string){
    const request=++loadRequest;loading=true;assetError='';mediaError='';navigationError='';navigationLoading=true;relationDialog=null;
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
  function previous(){const id=navigation.previousId??(fallbackIndex>0?assetIds[fallbackIndex-1]:null);if(id){mutations.clearOutcome();currentId=id}}
  function next(){const id=navigation.nextId??(fallbackIndex>=0&&fallbackIndex<assetIds.length-1?assetIds[fallbackIndex+1]:null);if(id){mutations.clearOutcome();currentId=id}}
  function target(id:string):AssetSelectionTarget{return{kind:'ids',ids:[id]}}
  async function reload(){if(currentId)await loadCurrent(currentId)}
  async function retryMedia(){if(!asset||mediaRefreshing)return;mediaRefreshing=true;mediaError='';try{media=await libraryData.media.refresh(asset,'view');mediaAttempt+=1}catch(error){mediaError=errorMessage(error,'Media could not be refreshed.')}finally{mediaRefreshing=false}}
  function markMediaFailed(){mediaError=asset?.is_offline?'The original source is offline and no usable cached preview is currently available.':'The media resource could not be loaded. It may be unavailable or the access URL may have expired.'}
  async function runAction(label:string,action:(id:string)=>Promise<MutationResult>){
    if(!asset||actionBusy)return;
    const id=asset.id;
    await mutations.run(label,()=>action(id),target(id));
  }
  async function favorite(){if(!asset)return;const next=!asset.is_favorite;await runAction(next?'Favorite':'Unfavorite',(id)=>libraryData.assets.setFavorite(target(id),next))}
  async function archive(){if(!asset)return;const next=!asset.is_archived;await runAction(next?'Archive':'Unarchive',(id)=>libraryData.assets.setArchived(target(id),next))}
  async function sync(){await runAction('Sync',(id)=>libraryData.assets.sync(target(id)))}
  async function removeTags(){await runAction('Remove tags',(id)=>libraryData.assets.removeTags(target(id)))}
  async function removeAlbums(){await runAction('Remove from albums',(id)=>libraryData.assets.removeFromAlbums(target(id)))}
  async function removeFromStack(){await runAction('Remove from stack',(id)=>libraryData.assets.unstack(target(id)))}
  async function setStackPrimary(){await runAction('Set stack primary',(id)=>libraryData.assets.setStackPrimary(id))}
  async function removeCompleteStack(){await runAction('Remove complete stack',(id)=>libraryData.assets.removeCompleteStack(id))}
  async function trash(){
    if(!asset||actionBusy)return;
    const id=asset.id;
    const fallback=navigation.nextId??navigation.previousId??(fallbackIndex>=0?(assetIds[fallbackIndex+1]??assetIds[fallbackIndex-1]??null):null);
    await mutations.run('Move to trash',()=>libraryData.assets.trash(target(id)),target(id),{
      refresh:async(result)=>{
        if(!result.affectedIds.includes(id))return;
        if(fallback&&await libraryData.assets.getById(fallback))currentId=fallback;else onclose();
      },
      refreshError:'The asset was moved to trash, but the viewer could not move to the next asset.',
    });
  }
  function selectedOptionValues(kind:'album'|'tag'){return kind==='album'?[relationAlbum].filter(Boolean):[...relationTags]}
  const searchAlbumOptions=(query:string,append=false)=>relations.searchAlbums(query,selectedOptionValues('album'),append);
  const searchTagOptions=(query:string,append=false)=>relations.searchTags(query,selectedOptionValues('tag'),append);
  function openRelationDialog(kind:RelationDialog){
    if(!kind||!asset||actionBusy)return;
    relationDialog=kind;relationAlbum='';relationTags=[];mutations.clearError();
    if(kind==='album')void searchAlbumOptions('');
    if(kind==='tags')void searchTagOptions('');
  }
  async function applyRelationDialog(){
    if(!asset||!relationDialog||actionBusy)return;
    const kind=relationDialog,id=asset.id;
    let result:MutationResult|null=null;
    if(kind==='album'&&relationAlbum)result=await mutations.run('Add to album',()=>libraryData.assets.addToAlbum(target(id),relationAlbum),target(id));
    if(kind==='tags'&&relationTags.length)result=await mutations.run('Add tags',()=>libraryData.assets.addTags(target(id),relationTags),target(id));
    if(result)relationDialog=null;
  }
  async function applyCreatedRelation(kind:'album'|'tag',value:string){
    if(!asset||actionBusy)return;
    const id=asset.id;
    if(kind==='album')await mutations.run('Add to album',()=>libraryData.assets.addToAlbum(target(id),value),target(id));
    else await mutations.run('Add tags',()=>libraryData.assets.addTags(target(id),[value]),target(id));
  }
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
  {#snippet header()}<V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Assets Viewer</b><V2Badge text={navigationLoading?'Locating…':positionLabel}/>{#if actionStatus}<V2Badge text={actionStatus}/>{/if}{#if asset?.is_offline}<V2Badge text="Source offline"/>{/if}{#if needsVideoProxy}<V2Badge text="Transcoded playback"/>{:else if needsDecodedImage}<V2Badge text="Decoded preview"/>{/if}</V2Inline><V2Inline gap="sm">{#if !isVideo}<V2ZoomControl value={camera.zoom} onzoomout={()=>camera.setZoom(camera.zoom/1.25)} onzoomin={()=>camera.setZoom(camera.zoom*1.25)}/><V2Button onclick={()=>camera.fit()} title="Reset zoom and fit image">Fit</V2Button><V2Button onclick={()=>camera.actual()} title="Actual pixel size">1:1</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></V2Inline>{/snippet}
  <div class="v2-viewer-stage"><div class="v2-image-stage">{#if loading}<span class="v2-muted">Loading asset…</span>{:else if assetError}<V2ErrorState title="Asset unavailable" message={assetError} onretry={()=>currentId&&void loadCurrent(currentId)}/>{:else if mediaError}<V2ErrorState title={asset?.is_offline?'Source offline':'Media unavailable'} message={mediaError} retryLabel={mediaRefreshing?'Refreshing…':'Retry media'} onretry={()=>void retryMedia()}/>{:else if asset&&media}{#key mediaAttempt}<V2MediaViewport resource={media} assetType={asset.asset_type} alt={asset.original_file_name} controller={camera} onerror={markMediaFailed}/>{/key}{/if}</div><aside class="v2-viewer-info">{#if actionError}<V2Section title="Action"><V2Card><span class="v2-small viewer-action-error">{actionError}</span></V2Card></V2Section>{/if}<V2OperationFeedback feedback={mutations.feedback} retryLabel={mutations.retry?'Retry failed':''} onretry={mutations.retry?()=>void mutations.retry?.():undefined}/>{#if navigationError}<V2Section title="Navigation"><V2Card><span class="v2-small v2-muted">{navigationError} Loaded-page navigation remains available when possible.</span></V2Card></V2Section>{/if}{#if asset}<V2Section title="Details"><V2Card><b>{asset.original_file_name}</b><p class="v2-small v2-muted">{asset.width??'—'} × {asset.height??'—'} · {asset.original_mime_type??'Unknown type'} · {sizeLabel}</p>{#if asset.is_offline}<p class="v2-small v2-muted">The original source is currently offline. A cached or generated derivative may still be viewable.</p>{/if}{#if needsVideoProxy}<p class="v2-small v2-muted">Original format is preserved in metadata; playback uses a browser-compatible derivative.</p>{:else if needsDecodedImage}<p class="v2-small v2-muted">Original format is preserved; viewing uses a decoded browser-compatible derivative.</p>{/if}</V2Card></V2Section><V2Section title="Metadata"><V2Card><span class="v2-small">Taken {new Date(asset.file_created_at).toLocaleString()}<br>{asset.library_id?'External library':'Default library'}<br>{asset.tags.length} tag{asset.tags.length===1?'':'s'}{asset.stack?` · stack of ${asset.stack.assetCount}`:''}</span></V2Card></V2Section><V2Section title="Relationships"><V2Card><span class="v2-small">{asset.tags.length?asset.tags.map((tag)=>tag.name).join(' · '):'No tags'}<br>{asset.is_favorite?'Favorite':'Not favorite'} · {asset.is_archived?'Archived':'Not archived'}</span>{#if asset.stack}<p class="v2-small v2-muted">Stack {asset.stack.id} · {isStackPrimary?'Primary asset':'Stack member'}</p>{/if}</V2Card></V2Section>{:else}<V2Section title="Asset"><V2Card><span class="v2-muted">This asset is no longer available in the current data source.</span></V2Card></V2Section>{/if}</aside></div>
  {#snippet footer()}<V2Button disabled={!canPrevious||navigationLoading||actionBusy} onclick={previous}>← Previous</V2Button><V2Inline gap="sm" wrap={true}><V2Button disabled={!asset||loading||actionBusy} onclick={favorite}>{asset?.is_favorite?'Unfavorite':'Favorite'}</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={archive}>{asset?.is_archived?'Unarchive':'Archive'}</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={()=>openRelationDialog('album')}>Album</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={()=>openRelationDialog('tags')}>Tags</V2Button><V2Button disabled={!asset||loading||actionBusy} onclick={sync}>Sync</V2Button>{#if asset?.tags.length}<V2Button disabled={actionBusy} onclick={removeTags}>Remove tags</V2Button>{/if}<V2Button disabled={!asset||loading||actionBusy} onclick={removeAlbums}>Remove from albums</V2Button>{#if asset?.stack}<V2Button disabled={actionBusy} onclick={removeFromStack}>Remove from stack</V2Button>{#if !isStackPrimary}<V2Button disabled={actionBusy} onclick={setStackPrimary}>Set stack primary</V2Button>{/if}<V2Button variant="danger" disabled={actionBusy} onclick={removeCompleteStack}>Remove complete stack</V2Button>{/if}<V2Button variant="danger" disabled={!asset||loading||actionBusy} onclick={trash}>Trash</V2Button></V2Inline><V2Button disabled={!canNext||navigationLoading||actionBusy} onclick={next}>Next →</V2Button>{/snippet}
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
  .viewer-action-error { color:var(--v2-danger,#e05a5a); }
</style>
