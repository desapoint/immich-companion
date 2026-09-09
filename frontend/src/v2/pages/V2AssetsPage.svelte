<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { Archive,ArchiveRestore,CheckCheck,FolderMinus,FolderPlus,Heart,HeartOff,Layers3,ListChecks,MoreHorizontal,RefreshCw,Star,Tag,Tags,Trash2,Unlink } from '@lucide/svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2AssetGrid from '../components/V2AssetGrid.svelte';
  import V2AssetRelationModal from '../components/V2AssetRelationModal.svelte';
  import V2AssetSearchDrawer from '../components/V2AssetSearchDrawer.svelte';
  import V2AssetSelectionToolbar from '../components/V2AssetSelectionToolbar.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2CollectionFooter from '../components/V2CollectionFooter.svelte';
  import V2ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import V2ErrorState from '../components/V2ErrorState.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2OperationFeedback from '../components/V2OperationFeedback.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2SavedSearchLibrary from '../components/V2SavedSearchLibrary.svelte';
  import V2SavedSearchModal from '../components/V2SavedSearchModal.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2SimpleAdvancedFilters from '../components/V2SimpleAdvancedFilters.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createGridViewportAnchor } from '../components/gridViewportAnchor';
  import { createAssetGridSelectionInteraction } from '../components/assetGridSelectionInteraction';
  import { applyShiftAssetRange,emptyAssetSelection,getAssetSelectionCount,invertAssetSelection,isAllVisibleSelected,isAssetSelected,selectAllMatchingAssets,selectVisibleAssets,toggleAssetSelected,type AssetSelectionState } from '../components/assetSelection';
  import { createCollectionView } from '../state/collectionView.svelte';
  import { AssetMutationController } from '../state/assetMutations.svelte';
  import { AssetRelationOptionsController } from '../state/assetRelationOptions.svelte';
  import { assetRulesInGroups,assetSearchCounts,buildAssetCriteria,cloneAssetGroups,emptyAssetAdvanced,emptyAssetSimple,hydrateAssetGroups,simpleAssetSearchToExpert,splitAssetIds,type AssetGroup,type AssetRule,type AssetSearchMode,type AssetSimpleSnapshot } from '../state/assetSearch';
  import { SavedSearchController } from '../state/savedSearches.svelte';
  import { CollectionRequestController } from '../state/collectionRequest.svelte';
  import { LatestRequestController } from '../state/latestRequest';
  import { scrollViewedAssetIntoView, viewerPageForPosition } from '../state/viewerCollectionNavigation';
  import { consumeV2AssetFilterHandoff } from '../navigation';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { AssetRecord, AssetSearchCriteria, AssetSearchQuery, AssetSelectionCapabilities, AssetSelectionTarget, SavedSearchRecord, ViewerNavigationWindow } from '../data/contracts';

  type AssetTab='Browse'|'Saved searches';
  type RelationDialog='album'|'tags'|null;
  const collection=createCollectionView({pageSize:24,columns:4,resultModeStorageKey:'immichCompanionResultMode'});
  const emptyCapabilities=():AssetSelectionCapabilities=>({count:0,allFavorite:false,allArchived:false,hasTags:false,hasAlbums:false,hasStackMembers:false,canStack:false,singleAssetId:null,canSetStackPrimary:false,canRemoveCompleteStack:false});

  let tab=$state<AssetTab>('Browse'),searchMode=$state<AssetSearchMode>('Simple'),appliedSearchMode=$state<AssetSearchMode>('Simple'),viewer=$state(false),viewerAssetId=$state<string|null>(null),viewerStartStack=$state(false),drawer=$state(false),saveSearchOpen=$state(false),selectedSaved=$state(''),sort=$state('takenDate:desc');
  let filename=$state(''),mediaType=$state(''),favorite=$state(''),archived=$state(''),simpleAdvanced=$state(emptyAssetAdvanced()),appliedSimple=$state<AssetSimpleSnapshot>(emptyAssetSimple());
  let assetGrid=$state<HTMLElement|null>(null),selection=$state<AssetSelectionState<string>>(emptyAssetSelection<string>()),moreOpen=$state(false),relationDialog=$state<RelationDialog>(null),relationAlbum=$state(''),relationTags=$state<string[]>([]),trashConfirmOpen=$state(false);
  let items=$state<AssetRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),selectionCapabilities=$state<AssetSelectionCapabilities>(emptyCapabilities()),selectionError=$state('');
  let seq=$state(0),groupSeq=$state(0),logic=$state<'AND'|'OR'>('AND'),negated=$state(false),rules=$state<AssetRule[]>([]),groups=$state<AssetGroup[]>([]);
  let appliedRules=$state<AssetRule[]>([]),appliedGroups=$state<AssetGroup[]>([]),appliedLogic=$state<'AND'|'OR'>('AND'),appliedNegated=$state(false),draftRules=$state<AssetRule[]>([]),draftGroups=$state<AssetGroup[]>([]),draftLogic=$state<'AND'|'OR'>('AND'),draftNegated=$state(false);
  let viewerLastId:string|null=null,viewerLastPosition:number|null=null,viewerCollectionSync:Promise<void>=Promise.resolve();

  const relations=new AssetRelationOptionsController();
  const savedSearches=new SavedSearchController();
  const searchRequests=new CollectionRequestController(),capabilityRequests=new LatestRequestController();
  const searching=$derived(searchRequests.loading),loadError=$derived(searchRequests.error);
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  const ids=$derived(items.map((asset)=>asset.id));
  const expressionCounts=$derived(assetSearchCounts(rules,groups));
  const savedSearchOptions=$derived(savedSearches.records.map((record)=>({value:record.id,label:record.name,subtitle:record.description||`${record.criteria.mode} search`})));
  const selectedCount=$derived(getAssetSelectionCount(selection,total)),selectionActive=$derived(selectedCount>0),allMatchingSelected=$derived(selection.allMatchingSelected),allVisibleSelected=$derived(isAllVisibleSelected(selection,ids));
  const favoriteActionLabel=$derived(selectionCapabilities.allFavorite?'Unfavorite':'Favorite'),archiveActionLabel=$derived(selectionCapabilities.allArchived?'Unarchive':'Archive');
  const hasRemovableTags=$derived(selectionCapabilities.hasTags),hasRemovableAlbums=$derived(selectionCapabilities.hasAlbums),hasStackMembers=$derived(selectionCapabilities.hasStackMembers);
  const canSetStackPrimary=$derived(selectionCapabilities.canSetStackPrimary),canRemoveCompleteStack=$derived(selectionCapabilities.canRemoveCompleteStack),singleSelectedId=$derived(selectionCapabilities.singleAssetId);
  const interaction=createAssetGridSelectionInteraction<string>({getItems:()=>ids,getSelection:()=>selection,setSelection:(next)=>selection=next,parseAssetId:(value)=>value});
  function criteria():AssetSearchCriteria{return buildAssetCriteria({sort,mode:appliedSearchMode,simple:appliedSimple,rules:appliedRules,groups:appliedGroups,logic:appliedLogic,negated:appliedNegated})}
  function draftCriteria():AssetSearchCriteria{return buildAssetCriteria({sort,mode:'Expert',simple:appliedSimple,rules:draftRules,groups:draftGroups,logic:draftLogic,negated:draftNegated})}
  function pageQuery(reset=true):AssetSearchQuery{const base=criteria();return collection.resultMode==='Pagination'?{...base,page:collection.page,pageSize:collection.pageSize}:{...base,pageSize:collection.pageSize,cursor:reset?null:nextCursor}}
  function selectionTarget():AssetSelectionTarget{return selection.allMatchingSelected?{kind:'query',criteria:criteria(),excludedIds:[...selection.excludedIds]}:{kind:'ids',ids:[...selection.selectedIds]}}
  async function refreshSelectionCapabilities(){if(!selectionActive){capabilityRequests.cancel();selectionCapabilities=emptyCapabilities();selectionError='';return}const request=capabilityRequests.begin();try{const result=await libraryData.assets.selectionCapabilities(selectionTarget(),request.signal);if(capabilityRequests.isCurrent(request)){selectionCapabilities=result;selectionError=''}}catch(error){if(capabilityRequests.isCurrent(request))selectionError=errorMessage(error,'Selection details could not be loaded.')}finally{capabilityRequests.finish(request)}}
  async function refreshSearch(reset=true):Promise<boolean>{
    if(searching&&!reset)return false;
    if(reset)nextCursor=null;
    const result=await searchRequests.run((signal)=>libraryData.assets.search({...pageQuery(reset),signal}),{
      fallbackError:'Assets could not be loaded.',
      mode:collection.resultMode==='Infinite'&&!reset?'append':'replace',
      apply:(response,mode)=>{
        items=mode==='append'?[...items,...response.items]:response.items;
        total=response.total;
        nextCursor=response.nextCursor;
        collection.clampPage(total);
      },
    });
    if(!result)return false;
    await refreshSelectionCapabilities();
    return true;
  }
  const mutations=new AssetMutationController(async()=>{if(!await refreshSearch(true))throw new Error(searchRequests.error||'Assets could not be refreshed.')},()=>{});

  async function loadMore(){if(collection.resultMode!=='Infinite'||!nextCursor||searching)return;collection.loadMore(total);await refreshSearch(false)}
  async function runSearch(){appliedSearchMode=searchMode;if(searchMode==='Simple')appliedSimple={filename,mediaType,favorite,archived,advanced:{...simpleAdvanced}};else{appliedRules=rules.map((rule)=>({...rule}));appliedGroups=cloneAssetGroups(groups);appliedLogic=logic;appliedNegated=negated}collection.reset();clearSelection();await refreshSearch(true)}
  function setPage(next:number){collection.setPage(next);void refreshSearch(true);document.querySelector<HTMLElement>('.v2-content')?.scrollTo({top:0,behavior:'smooth'})}
  function setAssetColumns(next:number|string){collection.setColumns(next);gridViewportAnchor.adjust()}
  function setSort(value:string){sort=value;collection.reset();void refreshSearch(true)}
  function setPageSize(value:number){collection.setPageSize(value,total);void refreshSearch(true)}
  function setMode(value:ResultMode){collection.setMode(value);collection.reset();void refreshSearch(true)}
  function openDrawer(){draftRules=rules.map((rule)=>({...rule}));draftGroups=cloneAssetGroups(groups);draftLogic=logic;draftNegated=negated;drawer=true}
  function convertSimpleToExpert(){const converted=simpleAssetSearchToExpert({filename,mediaType,favorite,archived,advanced:{...simpleAdvanced}},()=>++seq);rules=converted.rules;groups=converted.groups;logic=converted.logic;negated=converted.negated;searchMode='Expert';openDrawer()}
  function applyDrawer(){rules=draftRules.map((rule)=>({...rule}));groups=cloneAssetGroups(draftGroups);logic=draftLogic;negated=draftNegated;drawer=false;searchMode='Expert';void runSearch()}
  async function saveDraftSearch(name:string,description:string){const record=await savedSearches.saveCurrent(name,description,draftCriteria());if(record){selectedSaved=record.id;saveSearchOpen=false}}
  function applySavedSearch(record:SavedSearchRecord,execute=false){selectedSaved=record.id;const saved=record.criteria;sort=`${saved.sort.field}:${saved.sort.direction}`;if(saved.mode==='expert'){searchMode='Expert';rules=saved.rules.map((rule)=>({id:++seq,...rule}));groups=hydrateAssetGroups(saved.groups,()=>++seq,()=>++groupSeq);logic=saved.logic;negated=saved.negated}else{searchMode='Simple';filename=saved.filters.filename??'';mediaType=saved.filters.mediaType??'';favorite=saved.filters.favorite??'';archived=saved.filters.archived??'';simpleAdvanced={albumIds:(saved.filters.albumIds??[]).join(','),tagIds:(saved.filters.tagIds??[]).join(','),noAlbum:Boolean(saved.filters.noAlbum),noTag:Boolean(saved.filters.noTag),takenAfter:saved.filters.takenAfter??'',takenBefore:saved.filters.takenBefore??'',minWidth:saved.filters.minWidth??'',maxWidth:saved.filters.maxWidth??'',minHeight:saved.filters.minHeight??'',maxHeight:saved.filters.maxHeight??'',minAspectRatio:saved.filters.minAspectRatio??'',maxAspectRatio:saved.filters.maxAspectRatio??''}}clearSelection();if(execute)void runSearch()}
  async function loadSaved(value:string){selectedSaved=value;const record=savedSearches.records.find((item)=>item.id===value)??await savedSearches.get(value);if(record)applySavedSearch(record,false)}
  function openSaved(record:SavedSearchRecord){tab='Browse';applySavedSearch(record,true)}
  function assetSublabel(asset:AssetRecord){const state=[asset.is_archived?'Archived':null].filter(Boolean);state.push(new Date(asset.file_created_at).toLocaleDateString());return state.join(' · ')}
  function isSelected(id:string){return isAssetSelected(selection,id)}
  function clearSelection(){capabilityRequests.cancel();selection=emptyAssetSelection<string>();moreOpen=false;selectionCapabilities=emptyCapabilities();selectionError=''}
  function selectVisible(){selection=selectVisibleAssets(ids);void refreshSelectionCapabilities()}
  function selectAllMatching(){selection=selectAllMatchingAssets(ids[0]??null);void refreshSelectionCapabilities()}
  function invertSelection(){selection=invertAssetSelection(selection);void refreshSelectionCapabilities()}
  function handleSelectionClick(id:string,event:MouseEvent){selection=event.shiftKey?applyShiftAssetRange(selection,ids,id):toggleAssetSelected(selection,id);void refreshSelectionCapabilities()}
  function openViewer(id:string,startStack=false){const index=items.findIndex((item)=>item.id===id);viewerAssetId=id;viewerStartStack=startStack;viewerLastId=id;viewerLastPosition=index<0?null:collection.resultMode==='Pagination'?(collection.page-1)*collection.pageSize+index+1:index+1;viewer=true}
  async function synchronizeViewerCollection(id:string,navigation:ViewerNavigationWindow):Promise<void>{
    viewerLastId=id;
    if(navigation.position!==null)viewerLastPosition=navigation.position;
    const position=navigation.position??viewerLastPosition;
    if(position===null)return;
    if(collection.resultMode==='Pagination'){
      const targetPage=viewerPageForPosition(position,collection.pageSize);
      if(targetPage!==null&&(collection.page!==targetPage||!items.some((item)=>item.id===id))){collection.setPage(targetPage);await refreshSearch(true)}
      return;
    }
    while(!items.some((item)=>item.id===id)&&items.length<position&&nextCursor){const before=items.length;await refreshSearch(false);if(items.length===before)break}
  }
  function handleViewerNavigate(id:string,navigation:ViewerNavigationWindow):Promise<void>{const sync=synchronizeViewerCollection(id,navigation);viewerCollectionSync=sync.catch(()=>{});return sync}
  async function reconcileViewerMutation():Promise<void>{
    const previouslyLoaded=items.length;
    if(collection.resultMode==='Pagination'){await refreshSearch(true);return}
    if(!await refreshSearch(true))return;
    const targetLoaded=Math.min(previouslyLoaded,total);
    while(items.length<targetLoaded&&nextCursor){const before=items.length;if(!await refreshSearch(false)||items.length===before)break}
  }
  function closeViewer(){viewer=false;viewerStartStack=false;const id=viewerLastId;const pending=viewerCollectionSync;void(async()=>{await pending;await tick();scrollViewedAssetIntoView(assetGrid,id)})()}
  async function filterViewerRelationship(kind:'album'|'tag',id:string){viewer=false;viewerAssetId=null;viewerStartStack=false;tab='Browse';selectedSaved='';searchMode='Expert';rules=[{id:++seq,field:kind,op:'is',value:id}];groups=[];logic='AND';negated=false;await runSearch()}
  function handleTileActivate(id:string,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}openViewer(id)}
  async function setSelectedFavorite(){if(!selectionActive)return;const next=favoriteActionLabel==='Favorite';await mutations.run(next?'Favorite':'Unfavorite',(target)=>libraryData.assets.setFavorite(target,next),selectionTarget());moreOpen=false}
  async function setSelectedArchived(){if(!selectionActive)return;const next=archiveActionLabel==='Archive';await mutations.run(next?'Archive':'Unarchive',(target)=>libraryData.assets.setArchived(target,next),selectionTarget());moreOpen=false}
  async function trashSelected(){if(!selectionActive||mutations.busy)return;const result=await mutations.run('Move to trash',(target)=>libraryData.assets.trash(target),selectionTarget());trashConfirmOpen=false;if(result)clearSelection()}
  async function syncSelected(){await mutations.run('Sync',(target)=>libraryData.assets.sync(target),selectionTarget());moreOpen=false}
  async function removeTags(){await mutations.run('Remove tags',(target)=>libraryData.assets.removeTags(target),selectionTarget());moreOpen=false}
  async function removeAlbums(){await mutations.run('Remove from albums',(target)=>libraryData.assets.removeFromAlbums(target),selectionTarget());moreOpen=false}
  async function stackSelected(){if(!selectionCapabilities.canStack)return;await mutations.run('Stack assets',(target)=>libraryData.assets.stack(target),selectionTarget());moreOpen=false}
  async function removeFromStack(){await mutations.run('Remove from stack',(target)=>libraryData.assets.unstack(target),selectionTarget());moreOpen=false}
  async function setPrimary(){if(!singleSelectedId)return;await mutations.run('Set stack primary',()=>libraryData.assets.setStackPrimary(singleSelectedId),{kind:'ids',ids:[singleSelectedId]});moreOpen=false}
  async function removeCompleteStack(){if(!singleSelectedId)return;await mutations.run('Remove complete stack',()=>libraryData.assets.removeCompleteStack(singleSelectedId),{kind:'ids',ids:[singleSelectedId]});moreOpen=false}

  function selectedOptionValues(kind:'album'|'tag'){const field=kind==='album'?'album':'tag';const expert=[...rules,...assetRulesInGroups(groups),...draftRules,...assetRulesInGroups(draftGroups)].filter((rule)=>rule.field===field).flatMap((rule)=>splitAssetIds(rule.value));return kind==='album'?[relationAlbum,...splitAssetIds(simpleAdvanced.albumIds),...expert].filter(Boolean):[...relationTags,...splitAssetIds(simpleAdvanced.tagIds),...expert]}
  const searchAlbumOptions=(query:string,append=false)=>relations.searchAlbums(query,selectedOptionValues('album'),append);
  const searchTagOptions=(query:string,append=false)=>relations.searchTags(query,selectedOptionValues('tag'),append);
  function openRelationDialog(kind:RelationDialog){relationDialog=kind;relationAlbum='';relationTags=[];moreOpen=false;if(kind==='album')void searchAlbumOptions('');if(kind==='tags')void searchTagOptions('')}
  async function applyRelationDialog(){if(relationDialog==='album'&&relationAlbum)await mutations.run('Add to album',(target)=>libraryData.assets.addToAlbum(target,relationAlbum),selectionTarget());if(relationDialog==='tags'&&relationTags.length)await mutations.run('Add tags',(target)=>libraryData.assets.addTags(target,relationTags),selectionTarget());relationDialog=null}
  async function clearSearch(){filename='';mediaType='';favorite='';archived='';simpleAdvanced=emptyAssetAdvanced();rules=[];groups=[];appliedSimple=emptyAssetSimple();appliedRules=[];appliedGroups=[];appliedSearchMode=searchMode;selectedSaved='';collection.reset();clearSelection();await refreshSearch(true)}
  function handleWindowClick(event:MouseEvent){const target=event.target;if(moreOpen&&target instanceof Element&&!target.closest('.v2-selection-more'))moreOpen=false}
  async function consumeFilterHandoff(){const handoff=consumeV2AssetFilterHandoff();if(!handoff)return false;simpleAdvanced={...emptyAssetAdvanced(),albumIds:(handoff.albumIds??[]).join(','),tagIds:(handoff.tagIds??[]).join(',')};searchMode='Simple';await runSearch();return true}
  async function retryPageError(){mutations.clearError();relations.clearError();savedSearches.error='';selectionError='';searchRequests.clearError();await Promise.all([refreshSearch(true),searchAlbumOptions(relations.albumQuery),searchTagOptions(relations.tagQuery),savedSearches.refresh()])}
  onMount(()=>{void(async()=>{try{await libraryData.initialize();collection.hydrate();await Promise.all([searchAlbumOptions(''),searchTagOptions(''),savedSearches.refresh()]);if(!await consumeFilterHandoff())await refreshSearch(true)}catch(error){searchRequests.setError(errorMessage(error,'The asset data source could not be initialized.'))}})();return()=>{searchRequests.cancel();capabilityRequests.cancel();relations.destroy();gridViewportAnchor.destroy();interaction.destroy()}});
</script>

<svelte:window onclick={handleWindowClick} onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(event)=>{if(event.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(trashConfirmOpen){if(!mutations.busy)trashConfirmOpen=false}else if(relationDialog)relationDialog=null;else if(moreOpen)moreOpen=false;else if(saveSearchOpen){}else if(drawer)drawer=false;else if(viewer)closeViewer();else if(selectionActive)clearSelection()}}}/>

<V2PageLayout title="Assets" description="Search, browse, select and mutate assets through the active V2 data source.">
  {#snippet tabs()}<V2Tabs items={['Browse','Saved searches']} active={tab} ariaLabel="Asset sections" onselect={(value)=>tab=value as AssetTab}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Browse'}<V2Section title="Search mode"><V2Segmented items={['Simple','Expert']} active={searchMode} onselect={(value)=>searchMode=value as AssetSearchMode} ariaLabel="Search mode"/></V2Section>{#if searchMode==='Simple'}<V2Section title="Filters"><V2Stack gap="sm"><V2Field label="Filename" placeholder="Filename contains…" value={filename} onchange={(value)=>filename=value} onenter={(value)=>{filename=value;void runSearch()}}/><SelectField id="asset-media-type" label="Media type" allowEmpty placeholder="Any" bind:value={mediaType} options={['Image','Video']}/><SelectField id="asset-favorite" label="Favorite" allowEmpty placeholder="Any" bind:value={favorite} options={['Favorite','Not favorite']}/><SelectField id="asset-archived" label="Archived" allowEmpty placeholder="Any" bind:value={archived} options={['Archived','Not archived']}/><V2SimpleAdvancedFilters filters={simpleAdvanced} albumOptions={relations.albumOptions} tagOptions={relations.tagOptions} albumOptionsLoading={relations.albumLoading} tagOptionsLoading={relations.tagLoading} albumOptionsHasMore={Boolean(relations.albumCursor)} tagOptionsHasMore={Boolean(relations.tagCursor)} onalbumsearch={(value)=>void searchAlbumOptions(value)} ontagsearch={(value)=>void searchTagOptions(value)} onalbumloadmore={()=>void searchAlbumOptions(relations.albumQuery,true)} ontagloadmore={()=>void searchTagOptions(relations.tagQuery,true)} onchange={(next)=>simpleAdvanced=next}/></V2Stack></V2Section>{:else}<V2Section title="Expert search"><V2Stack gap="sm"><SelectField id="asset-saved-search" label="Saved search" allowEmpty searchable placeholder="Choose saved search…" bind:value={selectedSaved} options={savedSearchOptions} loading={savedSearches.loading} onchange={(value)=>void loadSaved(value)}/><V2Card><V2Stack gap="sm"><V2Inline justify="between"><b>Current expression</b><V2Badge text={`${expressionCounts.rules} search token${expressionCounts.rules===1?'':'s'} · ${expressionCounts.groups} group${expressionCounts.groups===1?'':'s'}`}/></V2Inline><V2Button block onclick={openDrawer}>Edit expression</V2Button></V2Stack></V2Card></V2Stack></V2Section>{/if}<V2Inline gap="sm"><V2Button variant="primary" disabled={searching||mutations.busy} onclick={()=>void runSearch()}>Search assets</V2Button><V2Button disabled={searching||mutations.busy} onclick={()=>void clearSearch()}>Clear</V2Button>{#if searchMode==='Simple'}<V2Button disabled={searching||mutations.busy} onclick={convertSimpleToExpert}>Convert to expert</V2Button>{/if}</V2Inline>{:else}<V2Section title="Saved search library"><span class="v2-small v2-muted">Create, edit, delete and open searches stored by the active data source.</span></V2Section>{/if}</V2Zone>{/snippet}

  <V2Zone>{#if tab==='Browse'}
    {#if loadError||selectionError||mutations.error||relations.error||savedSearches.error}<V2ErrorState title="Asset operation failed" message={loadError||selectionError||mutations.error||relations.error||savedSearches.error} onretry={()=>void retryPageError()}/>{/if}
    <V2OperationFeedback feedback={mutations.feedback} retryLabel={mutations.retry?'Retry failed':''} onretry={mutations.retry?()=>void mutations.retry?.():undefined}/>
    {#if selectionActive}<V2AssetSelectionToolbar {selectedCount} {total} noun="matching assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>{#snippet actions()}<V2Button iconOnly title="Add to album" ariaLabel="Add to album" disabled={mutations.busy} onclick={()=>openRelationDialog('album')}><FolderPlus size={18}/></V2Button><V2Button iconOnly title={favoriteActionLabel} ariaLabel={favoriteActionLabel} disabled={mutations.busy} onclick={setSelectedFavorite}>{#if favoriteActionLabel==='Unfavorite'}<HeartOff size={18}/>{:else}<Heart size={18}/>{/if}</V2Button><V2Button iconOnly variant="danger" title="Move to trash" ariaLabel="Move to trash" disabled={mutations.busy} onclick={()=>trashConfirmOpen=true}><Trash2 size={18}/></V2Button><div class="v2-selection-more"><V2Button iconOnly title="More actions" ariaLabel="More actions" active={moreOpen} disabled={mutations.busy} onclick={()=>moreOpen=!moreOpen}><MoreHorizontal size={18}/></V2Button>{#if moreOpen}<div class="v2-selection-menu" role="menu"><button type="button" disabled={mutations.busy} onclick={syncSelected}><RefreshCw size={17}/><span>Bulk Sync</span></button><div class="v2-selection-menu-separator"></div><button type="button" disabled={mutations.busy} onclick={()=>openRelationDialog('tags')}><Tags size={17}/><span>Add tags</span></button><button type="button" disabled={mutations.busy||!hasRemovableTags} onclick={removeTags}><Tag size={17}/><span>Remove tags</span></button><button type="button" disabled={mutations.busy||!hasRemovableAlbums} onclick={removeAlbums}><FolderMinus size={17}/><span>Remove from album</span></button><div class="v2-selection-menu-separator"></div><span class="v2-selection-menu-label">Stack actions</span><button type="button" disabled={mutations.busy||!selectionCapabilities.canStack} onclick={stackSelected}><Layers3 size={17}/><span>Stack selected</span></button>{#if canSetStackPrimary}<button type="button" disabled={mutations.busy} onclick={setPrimary}><Star size={17}/><span>Set as stack primary</span></button>{/if}<button type="button" disabled={mutations.busy||!hasStackMembers} onclick={removeFromStack}><Unlink size={17}/><span>Remove from stack</span></button>{#if canRemoveCompleteStack}<button type="button" disabled={mutations.busy} onclick={removeCompleteStack}><Layers3 size={17}/><span>Remove complete stack</span></button>{/if}<div class="v2-selection-menu-separator"></div><button type="button" disabled={mutations.busy} onclick={setSelectedArchived}>{#if archiveActionLabel==='Unarchive'}<ArchiveRestore size={17}/>{:else}<Archive size={17}/>{/if}<span>{archiveActionLabel}</span></button></div>{/if}</div>{/snippet}</V2AssetSelectionToolbar>{:else}<V2Toolbar><V2Badge text={`${total.toLocaleString()} matches`}/>{#if searching}<V2Badge text="Searching…"/>{/if}<V2Button iconOnly title="Select visible" ariaLabel="Select visible" onclick={selectVisible}><ListChecks size={18}/></V2Button><V2Button iconOnly title={`Select all ${total.toLocaleString()} matching assets`} ariaLabel={`Select all ${total.toLocaleString()} matching assets`} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>{#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} value={collection.columns} valueLabel={`${collection.columns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(collection.columns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="asset-results" {sort} sortFields={[{value:'takenDate',label:'Taken date'},{value:'filename',label:'Filename'}]} pageSize={collection.pageSize} pageSizes={[24,48,96]} resultMode={collection.resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>{/if}
    <V2AssetGrid columns={collection.columns} bind:element={assetGrid}>{#each items as asset,index (asset.id)}<V2AssetTile index={collection.resultMode==='Pagination'?(collection.page-1)*collection.pageSize+index:index} assetId={asset.id} label={asset.original_file_name} sublabel={assetSublabel(asset)} favorite={asset.is_favorite} tags={asset.tags.map((tag)=>tag.name)} albums={(asset.albums??[]).map((album)=>album.name)} stackCount={asset.stack?.assetCount??0} image={()=>libraryData.media.thumbnail(asset)} selected={isSelected(asset.id)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(asset.id,event)} onselect={(event)=>handleSelectionClick(asset.id,event)} onpreview={()=>openViewer(asset.id)} onstackview={()=>openViewer(asset.id,true)} onpointerdown={(event)=>interaction.start(asset.id,event)}/>{/each}</V2AssetGrid><V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={items.length} noun="assets" onpage={setPage} onloadmore={loadMore}/>
  {:else}<V2SavedSearchLibrary controller={savedSearches} currentCriteria={criteria()} onopen={openSaved}/>{/if}</V2Zone>
</V2PageLayout>

<V2Viewer open={viewer} mode="assets" assetId={viewerAssetId} assetIds={ids} resultMode={collection.resultMode} collectionPage={collection.page} collectionPageSize={collection.pageSize} collectionTotal={total} startStack={viewerStartStack} onclose={closeViewer} onnavigate={handleViewerNavigate} onmutated={reconcileViewerMutation} onfilterrelation={filterViewerRelationship}/>
{#if trashConfirmOpen}<V2ConfirmDialog title="Move selected assets to trash?" message={`${selectedCount.toLocaleString()} selected asset${selectedCount===1?'':'s'} will be moved to trash.`} confirmLabel="Move to trash" icon="trash" destructive pending={mutations.busy} onconfirm={()=>void trashSelected()} onclose={()=>{if(!mutations.busy)trashConfirmOpen=false}}/>{/if}
{#if relationDialog}<V2AssetRelationModal kind={relationDialog} {selectedCount} albumValue={relationAlbum} tagValues={relationTags} albumOptions={relations.albumOptions} tagOptions={relations.tagOptions} albumLoading={relations.albumLoading} tagLoading={relations.tagLoading} albumHasMore={Boolean(relations.albumCursor)} tagHasMore={Boolean(relations.tagCursor)} busy={mutations.busy} onalbumchange={(value)=>relationAlbum=value} ontagschange={(values)=>relationTags=values} onalbumsearch={(value)=>void searchAlbumOptions(value)} ontagsearch={(value)=>void searchTagOptions(value)} onalbumloadmore={()=>void searchAlbumOptions(relations.albumQuery,true)} ontagloadmore={()=>void searchTagOptions(relations.tagQuery,true)} onclose={()=>relationDialog=null} onapply={()=>void applyRelationDialog()}/>{/if}
{#if drawer}<V2AssetSearchDrawer bind:rules={draftRules} bind:groups={draftGroups} bind:logic={draftLogic} bind:negated={draftNegated} albumOptions={relations.albumOptions} tagOptions={relations.tagOptions} albumLoading={relations.albumLoading} tagLoading={relations.tagLoading} albumHasMore={Boolean(relations.albumCursor)} tagHasMore={Boolean(relations.tagCursor)} onalbumsearch={(value)=>void searchAlbumOptions(value)} ontagsearch={(value)=>void searchTagOptions(value)} onalbumloadmore={()=>void searchAlbumOptions(relations.albumQuery,true)} ontagloadmore={()=>void searchTagOptions(relations.tagQuery,true)} onclose={()=>drawer=false} onsave={()=>saveSearchOpen=true} onapply={applyDrawer}/>{/if}
{#if saveSearchOpen}<V2SavedSearchModal title="Save expert search" busy={savedSearches.busy} onclose={()=>saveSearchOpen=false} onsave={(name,description)=>void saveDraftSearch(name,description)}/>{/if}

<style>:global(.v2-selection-toolbar .v2-toolbar-group){flex-wrap:wrap}.v2-selection-more{position:relative}.v2-selection-menu{position:absolute;z-index:30;top:calc(100% + .4rem);right:0;min-width:14.5rem;display:grid;gap:.18rem;padding:.4rem;border:1px solid var(--v2-border,rgba(127,127,127,.32));border-radius:.65rem;background:var(--v2-surface,Canvas);box-shadow:0 .65rem 1.8rem rgba(0,0,0,.18)}.v2-selection-menu button{border:0;border-radius:.45rem;background:transparent;color:inherit;padding:.55rem .65rem;text-align:left;font:inherit;cursor:pointer;display:flex;align-items:center;gap:.6rem}.v2-selection-menu button:hover:not(:disabled){background:color-mix(in srgb,currentColor 8%,transparent)}.v2-selection-menu button:disabled{opacity:.42;cursor:not-allowed}.v2-selection-menu-separator{height:1px;background:var(--v2-border,rgba(127,127,127,.28));margin:.25rem 0}.v2-selection-menu-label{padding:.35rem .65rem .15rem;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;opacity:.62}</style>
