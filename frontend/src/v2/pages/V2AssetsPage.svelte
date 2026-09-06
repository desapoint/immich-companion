<script lang="ts">
  import { onMount } from 'svelte';
  import { FolderMinus,FolderPlus,Archive,ArchiveRestore,CheckCheck,Heart,HeartOff,Layers3,ListChecks,MoreHorizontal,RefreshCw,Star,Tag,Tags,Trash2,Unlink } from '@lucide/svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2AssetGrid from '../components/V2AssetGrid.svelte';
  import V2AssetSelectionToolbar from '../components/V2AssetSelectionToolbar.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2CollectionControls from '../components/V2CollectionControls.svelte';
  import V2CollectionFooter from '../components/V2CollectionFooter.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2SimpleAdvancedFilters from '../components/V2SimpleAdvancedFilters.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2ZoneLabel from '../components/V2ZoneLabel.svelte';
  import { createGridViewportAnchor } from '../components/gridViewportAnchor';
  import { createAssetGridSelectionInteraction } from '../components/assetGridSelectionInteraction';
  import { applyShiftAssetRange,emptyAssetSelection,getAssetSelectionCount,invertAssetSelection,isAllVisibleSelected,isAssetSelected,selectAllMatchingAssets,selectVisibleAssets,toggleAssetSelected,type AssetSelectionState } from '../components/assetSelection';
  import { createCollectionView } from '../state/collectionView.svelte';
  import { demoAssetState,indexedDemoAssets,initializeDemoAssetState,selectedDemoAssetIds,setDemoAssetsFavorite,trashDemoAssets,type DemoAssetRecord } from '../demo/demoAssetState.svelte';

  type AssetTab='Browse'|'Saved searches';
  type Rule={id:number;field:string;op:string;value:string};
  type Group={id:number;logic:'AND'|'OR';negated:boolean;rules:Rule[]};
  const fieldOptions=[['filename','Filename'],['mediaType','Media type'],['favorite','Favorite'],['archived','Archived'],['album','Album'],['tag','Tag'],['takenDate','Taken date'],['width','Width'],['height','Height'],['aspectRatio','Aspect ratio']] as const;
  const operatorOptions=[['is','is'],['isNot','is not'],['contains','contains'],['notContains','does not contain'],['gt','greater than'],['gte','at least'],['lt','less than'],['lte','at most']] as const;
  const fieldSelectOptions=fieldOptions.map(([value,label])=>({value,label}));
  const operatorSelectOptions=operatorOptions.map(([value,label])=>({value,label}));
  const savedSearches=['Favorite images not archived','Family album or Vacation tag','Large landscape images'];
  const collection=createCollectionView({pageSize:24,columns:4,resultModeStorageKey:'immichCompanionResultMode'});
  const emptySimpleAdvancedFilters=()=>({albumIds:'',tagIds:'',noAlbum:false,noTag:false,takenAfter:'',takenBefore:'',minWidth:'',maxWidth:'',minHeight:'',maxHeight:'',minAspectRatio:'',maxAspectRatio:''});

  let tab=$state<AssetTab>('Browse'),searchMode=$state<'Simple'|'Expert'>('Simple'),viewer=$state(false),drawer=$state(false),summary=$state('Simple search · current filters'),selectedSaved=$state(savedSearches[0]),sort=$state('takenDate:desc');
  let mediaType=$state(''),favorite=$state(''),archived=$state(''),simpleAdvanced=$state(emptySimpleAdvancedFilters());
  let assetGrid=$state<HTMLElement|null>(null),selection=$state<AssetSelectionState<string>>(emptyAssetSelection<string>()),moreOpen=$state(false);
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  let seq=$state(4),groupSeq=$state(2),logic=$state<'AND'|'OR'>('AND'),negated=$state(false),rules=$state<Rule[]>([{id:1,field:'mediaType',op:'is',value:'Image'},{id:2,field:'favorite',op:'is',value:'true'}]),groups=$state<Group[]>([{id:2,logic:'OR',negated:false,rules:[{id:3,field:'album',op:'is',value:'Family'},{id:4,field:'tag',op:'is',value:'Vacation'}]}]);
  let draftRules=$state<Rule[]>([]),draftGroups=$state<Group[]>([]),draftLogic=$state<'AND'|'OR'>('AND'),draftNegated=$state(false);

  const matchingAssets=$derived((demoAssetState.revision,indexedDemoAssets()));
  const total=$derived(matchingAssets.length);
  const matchingIds=$derived(matchingAssets.map((asset)=>asset.id));
  const start=$derived(collection.firstIndex()),count=$derived(collection.visibleCount(total));
  const items=$derived(collection.resultMode==='Pagination'?matchingAssets.slice(start,start+count):matchingAssets.slice(0,count));
  const ids=$derived(items.map((asset)=>asset.id));
  const expression=$derived(expressionText(rules,groups,logic,negated)),draftExpression=$derived(expressionText(draftRules,draftGroups,draftLogic,draftNegated));
  const selectedIds=$derived(selectedDemoAssetIds(selection,matchingIds));
  const selectedCount=$derived(getAssetSelectionCount(selection,total)),selectionActive=$derived(selectedCount>0),allMatchingSelected=$derived(selection.allMatchingSelected),allVisibleSelected=$derived(isAllVisibleSelected(selection,ids)),explicitSelected=$derived([...selection.selectedIds]);
  const favoriteActionLabel=$derived(selectedIds.length>0&&selectedIds.every((id)=>matchingAssets.find((asset)=>asset.id===id)?.is_favorite)?'Unfavorite':'Favorite');
  const archiveActionLabel=$derived(selectedIds.length>0&&selectedIds.every((id)=>matchingAssets.find((asset)=>asset.id===id)?.is_archived)?'Unarchive':'Archive');
  const hasRemovableTags=$derived(allMatchingSelected||explicitSelected.some((_id,index)=>index%2===0)),hasRemovableAlbums=$derived(allMatchingSelected||explicitSelected.some((_id,index)=>index%4===0)),hasStackMembers=$derived(allMatchingSelected||explicitSelected.some((_id,index)=>index%6===0));
  const singleSelectedId=$derived(!allMatchingSelected&&explicitSelected.length===1?explicitSelected[0]:null),singleSelectedIndex=$derived(singleSelectedId===null?-1:matchingIds.indexOf(singleSelectedId)),canSetStackPrimary=$derived(singleSelectedIndex>=0&&singleSelectedIndex%6===0&&singleSelectedIndex%12!==0),canRemoveCompleteStack=$derived(singleSelectedIndex>=0&&singleSelectedIndex%6===0);
  const interaction=createAssetGridSelectionInteraction<string>({getItems:()=>ids,getSelection:()=>selection,setSelection:(next)=>selection=next,parseAssetId:(value)=>value});

  const fieldLabel=(value:string)=>fieldOptions.find(([key])=>key===value)?.[1]??value,operatorLabel=(value:string)=>operatorOptions.find(([key])=>key===value)?.[1]??value;
  function ruleText(r:Rule){return `${fieldLabel(r.field)} ${operatorLabel(r.op)} ${r.value||'…'}`}
  function expressionText(rs:Rule[],gs:Group[],root:'AND'|'OR',not:boolean){const base=`(${rs.map(ruleText).join(` ${root} `)||'empty'})`,nested=gs.map(g=>`${g.negated?'NOT ':''}(${g.rules.map(ruleText).join(` ${g.logic} `)||'empty'})`),text=[base,...nested].join(` ${root} `);return not?`NOT (${text})`:text}
  function setPage(next:number){collection.setPage(next);document.querySelector<HTMLElement>('.v2-content')?.scrollTo({top:0,behavior:'smooth'})}
  function setAssetColumns(next:number|string){collection.setColumns(next);gridViewportAnchor.adjust()}
  function openDrawer(){draftRules=rules.map(r=>({...r}));draftGroups=groups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));draftLogic=logic;draftNegated=negated;drawer=true}
  function applyDrawer(){rules=draftRules.map(r=>({...r}));groups=draftGroups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));logic=draftLogic;negated=draftNegated;drawer=false;summary=`Expert search · ${expressionText(rules,groups,logic,negated)}`;clearSelection()}
  function resetDraft(){draftRules=[];draftGroups=[];draftLogic='AND';draftNegated=false}
  function addRule(group?:Group){const rule={id:++seq,field:'filename',op:'contains',value:''};if(group)group.rules=[...group.rules,rule];else draftRules=[...draftRules,rule]}
  function removeRule(id:number,group?:Group){if(group)group.rules=group.rules.filter(r=>r.id!==id);else draftRules=draftRules.filter(r=>r.id!==id)}
  function addGroup(){draftGroups=[...draftGroups,{id:++groupSeq,logic:'AND',negated:false,rules:[{id:++seq,field:'tag',op:'is',value:''}]}]}
  function loadSaved(value:string){selectedSaved=value;if(value.includes('Favorite')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'},{id:++seq,field:'favorite',op:'is',value:'true'},{id:++seq,field:'archived',op:'is',value:'false'}];groups=[]}else if(value.includes('Family')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'}];groups=[{id:++groupSeq,logic:'OR',negated:false,rules:[{id:++seq,field:'album',op:'is',value:'Family'},{id:++seq,field:'tag',op:'is',value:'Vacation'}]}]}else if(value.includes('Large')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'},{id:++seq,field:'width',op:'gte',value:'3000'},{id:++seq,field:'aspectRatio',op:'gt',value:'1'}];groups=[]}summary='Expert draft · '+expressionText(rules,groups,logic,negated);clearSelection()}
  function assetSublabel(asset:DemoAssetRecord){const state=[asset.is_favorite?'Favorite':null,asset.is_archived?'Archived':null].filter(Boolean);state.push(new Date(asset.file_created_at).toLocaleDateString());return state.join(' · ')}
  function isSelected(id:string){return isAssetSelected(selection,id)}
  function clearSelection(){selection=emptyAssetSelection<string>();moreOpen=false}
  function selectVisible(){selection=selectVisibleAssets(ids)}
  function selectAllMatching(){selection=selectAllMatchingAssets(ids[0]??null)}
  function invertSelection(){selection=invertAssetSelection(selection)}
  function handleSelectionClick(id:string,event:MouseEvent){selection=event.shiftKey?applyShiftAssetRange(selection,ids,id):toggleAssetSelected(selection,id)}
  function handleTileActivate(id:string,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}viewer=true}
  function setSelectedFavorite(){if(selectedIds.length===0)return;const next=favoriteActionLabel==='Favorite';setDemoAssetsFavorite(selectedIds,next);summary=`Demo · ${selectedIds.length.toLocaleString()} asset${selectedIds.length===1?'':'s'} ${next?'favorited':'unfavorited'}`;moreOpen=false}
  function trashSelected(){if(selectedIds.length===0)return;const affected=selectedIds.length,remaining=Math.max(0,total-affected);trashDemoAssets(selectedIds);clearSelection();collection.clampPage(remaining);summary=`Demo · ${affected.toLocaleString()} asset${affected===1?'':'s'} moved to trash`}
  function demoAction(_label:string){moreOpen=false}
  function clearSearch(){summary=`${searchMode} search · cleared and reloaded`;mediaType='';favorite='';archived='';if(searchMode==='Simple')simpleAdvanced=emptySimpleAdvancedFilters();else{rules=[];groups=[]}clearSelection()}
  function handleWindowClick(event:MouseEvent){const target=event.target;if(moreOpen&&target instanceof Element&&!target.closest('.v2-selection-more'))moreOpen=false}
  onMount(()=>{initializeDemoAssetState();collection.hydrate();collection.clampPage(total);return()=>{gridViewportAnchor.destroy();interaction.destroy()}});
</script>

<svelte:window onclick={handleWindowClick} onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(e)=>{if(e.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(moreOpen)moreOpen=false;else if(drawer)drawer=false;else if(viewer)viewer=false;else if(selectionActive)clearSelection()}}}/>

<V2PageLayout title="Assets" description="Search, browse, select, synchronize and perform guarded actions on assets.">
  {#snippet tabs()}<V2Tabs items={['Browse','Saved searches']} active={tab} ariaLabel="Asset sections" onselect={(value)=>tab=value as AssetTab}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Browse'}<V2Section title="Search mode"><V2Segmented items={['Simple','Expert']} active={searchMode} onselect={(value)=>searchMode=value as 'Simple'|'Expert'} ariaLabel="Search mode"/></V2Section>{#if searchMode==='Simple'}<V2Section title="Filters"><V2Stack gap="sm"><V2Field label="Filename" placeholder="Filename contains…"/><SelectField id="asset-media-type" label="Media type" allowEmpty placeholder="Any" bind:value={mediaType} options={['Image','Video']}/><SelectField id="asset-favorite" label="Favorite" allowEmpty placeholder="Any" bind:value={favorite} options={['Favorite','Not favorite']}/><SelectField id="asset-archived" label="Archived" allowEmpty placeholder="Any" bind:value={archived} options={['Archived','Not archived']}/><V2SimpleAdvancedFilters filters={simpleAdvanced} onchange={(next)=>simpleAdvanced=next}/></V2Stack></V2Section>{:else}<V2Section title="Expert search">{#snippet actions()}<V2Badge text="Boolean"/>{/snippet}<V2Stack gap="sm"><SelectField id="asset-saved-search" label="Saved expert search" allowEmpty placeholder="Choose saved search…" options={savedSearches} onchange={loadSaved}/><V2Card><V2Stack gap="sm"><V2Inline justify="between"><b>Current expression</b><V2Badge text={`${rules.length+groups.reduce((n,g)=>n+g.rules.length,0)} rules · ${groups.length} groups`}/></V2Inline><span class="v2-small v2-muted">{expression}</span><V2Button block onclick={openDrawer}>Edit expression</V2Button></V2Stack></V2Card></V2Stack></V2Section>{/if}<V2Inline gap="sm"><V2Button variant="primary" onclick={()=>{summary=searchMode==='Expert'?`Expert search · ${expression}`:'Simple search · submitted filters';clearSelection()}}>Search assets</V2Button><V2Button onclick={clearSearch}>Clear</V2Button></V2Inline>{:else}<V2Section title="Saved search library"><V2Stack gap="sm"><SelectField id="asset-saved-library" label="Selected search" value={selectedSaved} options={savedSearches} onchange={(value)=>selectedSaved=value}/><V2Button variant="primary" onclick={()=>{loadSaved(selectedSaved);tab='Browse';searchMode='Expert'}}>Open in Browse</V2Button></V2Stack></V2Section>{/if}</V2Zone>{/snippet}

  <V2Zone>
    {#if tab==='Browse'}
      {#if selectionActive}
        <V2AssetSelectionToolbar {selectedCount} {total} noun="matching assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>
          {#snippet actions()}
            <V2Button iconOnly title="Add to album" ariaLabel="Add to album" onclick={()=>demoAction('Add to album')}><FolderPlus size={18}/></V2Button>
            <V2Button iconOnly title={favoriteActionLabel} ariaLabel={favoriteActionLabel} onclick={setSelectedFavorite}>{#if favoriteActionLabel==='Unfavorite'}<HeartOff size={18}/>{:else}<Heart size={18}/>{/if}</V2Button>
            <V2Button iconOnly variant="danger" title="Move to trash" ariaLabel="Move to trash" onclick={trashSelected}><Trash2 size={18}/></V2Button>
            <div class="v2-selection-more"><V2Button iconOnly title="More actions" ariaLabel="More actions" active={moreOpen} onclick={()=>moreOpen=!moreOpen}><MoreHorizontal size={18}/></V2Button>{#if moreOpen}<div class="v2-selection-menu" role="menu"><button type="button" onclick={()=>demoAction('Bulk Sync')}><RefreshCw size={17}/><span>Bulk Sync</span></button><div class="v2-selection-menu-separator"></div><button type="button" onclick={()=>demoAction('Add tags')}><Tags size={17}/><span>Add tags</span></button><button type="button" disabled={!hasRemovableTags} onclick={()=>demoAction('Remove tags')}><Tag size={17}/><span>Remove tags</span></button><button type="button" disabled={!hasRemovableAlbums} onclick={()=>demoAction('Remove from album')}><FolderMinus size={17}/><span>Remove from album</span></button><div class="v2-selection-menu-separator"></div><span class="v2-selection-menu-label">Stack actions</span><button type="button" disabled={selectedCount<2} onclick={()=>demoAction('Stack selected')}><Layers3 size={17}/><span>Stack selected</span></button>{#if canSetStackPrimary}<button type="button" onclick={()=>demoAction('Set as stack primary')}><Star size={17}/><span>Set as stack primary</span></button>{/if}<button type="button" disabled={!hasStackMembers} onclick={()=>demoAction('Remove from stack')}><Unlink size={17}/><span>Remove from stack</span></button>{#if canRemoveCompleteStack}<button type="button" onclick={()=>demoAction('Remove complete stack')}><Layers3 size={17}/><span>Remove complete stack</span></button>{/if}<div class="v2-selection-menu-separator"></div><button type="button" onclick={()=>demoAction(archiveActionLabel)}>{#if archiveActionLabel==='Unarchive'}<ArchiveRestore size={17}/>{:else}<Archive size={17}/>{/if}<span>{archiveActionLabel}</span></button></div>{/if}</div>
          {/snippet}
        </V2AssetSelectionToolbar>
      {:else}
        <V2Toolbar><V2Badge text={`${total.toLocaleString()} matches`}/><V2Badge text={summary}/><V2Button iconOnly title="Select visible" ariaLabel="Select visible" onclick={selectVisible}><ListChecks size={18}/></V2Button><V2Button iconOnly title={`Select all ${total.toLocaleString()} matching assets`} ariaLabel={`Select all ${total.toLocaleString()} matching assets`} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>{#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} value={collection.columns} valueLabel={`${collection.columns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(collection.columns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="asset-results" {sort} sortFields={[{value:'takenDate',label:'Taken date'},{value:'filename',label:'Filename'}]} pageSize={collection.pageSize} pageSizes={[24,48,96]} resultMode={collection.resultMode} onsort={(value)=>sort=value} onpagesize={(value)=>collection.setPageSize(value,total)} onmode={collection.setMode}/>{/snippet}</V2Toolbar>
      {/if}
      <V2AssetGrid columns={collection.columns} bind:element={assetGrid}>{#each items as asset,index}<V2AssetTile index={collection.resultMode==='Pagination'?start+index:index} assetId={asset.id} label={asset.original_file_name} sublabel={assetSublabel(asset)} selected={isSelected(asset.id)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(asset.id,event)} onselect={(event)=>handleSelectionClick(asset.id,event)} onpreview={()=>viewer=true} onpointerdown={(event)=>interaction.start(asset.id,event)}/>{/each}</V2AssetGrid>
      <V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={collection.loaded} noun="assets" onpage={setPage} onloadmore={()=>collection.loadMore(total)}/>
    {:else}<V2Toolbar sticky={false}><V2Badge text={`${savedSearches.length} saved searches`}/>{#snippet actions()}<V2Button variant="primary">Create saved search</V2Button>{/snippet}</V2Toolbar><V2Stack gap="sm">{#each savedSearches as saved}<V2Card><V2Inline justify="between" wrap><V2Stack gap="xs"><b>{saved}</b><span class="v2-small v2-muted">Reusable expert-search definition</span></V2Stack><V2Inline gap="sm"><V2Button onclick={()=>selectedSaved=saved}>Select</V2Button><V2Button onclick={()=>{selectedSaved=saved;loadSaved(saved);tab='Browse';searchMode='Expert'}}>Open</V2Button></V2Inline></V2Inline></V2Card>{/each}</V2Stack>{/if}
  </V2Zone>
</V2PageLayout>

<V2Viewer open={viewer} title="Assets Viewer" mode="assets" onclose={()=>viewer=false}/>
{#if drawer}<button type="button" class="v2-drawer-backdrop" aria-label="Close expert search editor" onclick={()=>drawer=false}></button><aside class="v2-drawer"><div class="v2-drawer-head"><div><V2ZoneLabel text="Expert search editor"/><h2>Build asset search expression</h2><p class="v2-muted">Edit the draft here. Results change only when you apply/search.</p></div><V2Button onclick={()=>drawer=false}>✕</V2Button></div><div class="v2-drawer-body"><V2Section title="Expression structure"><V2Stack gap="md"><V2Card><V2Stack gap="sm"><V2Inline justify="between" wrap><V2Inline gap="sm"><V2Badge text="Root group"/><V2Segmented items={['AND','OR']} active={draftLogic} onselect={(value)=>draftLogic=value as 'AND'|'OR'} ariaLabel="Root group logic"/><V2Checkbox label="NOT group" checked={draftNegated} onchange={(checked)=>draftNegated=checked}/></V2Inline></V2Inline>{#each draftRules as rule}<div class="v2-expert-rule"><SelectField id={`expert-root-field-${rule.id}`} value={rule.field} options={fieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-root-op-${rule.id}`} value={rule.op} options={operatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value} placeholder="Value…"><V2Button onclick={()=>removeRule(rule.id)}>✕</V2Button></div>{/each}<V2Inline gap="sm"><V2Button onclick={()=>addRule()}>+ Rule</V2Button><V2Button onclick={addGroup}>+ Nested group</V2Button></V2Inline></V2Stack></V2Card>{#each draftGroups as group}<V2Card><V2Stack gap="sm"><V2Inline justify="between"><V2Inline gap="sm"><V2Badge text="Nested group"/><V2Segmented items={['AND','OR']} active={group.logic} onselect={(value)=>group.logic=value as 'AND'|'OR'} ariaLabel="Nested group logic"/><V2Checkbox label="NOT group" checked={group.negated} onchange={(checked)=>group.negated=checked}/></V2Inline><V2Button onclick={()=>draftGroups=draftGroups.filter(g=>g.id!==group.id)}>Remove group</V2Button></V2Inline>{#each group.rules as rule}<div class="v2-expert-rule"><SelectField id={`expert-group-${group.id}-field-${rule.id}`} value={rule.field} options={fieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-group-${group.id}-op-${rule.id}`} value={rule.op} options={operatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value}><V2Button onclick={()=>removeRule(rule.id,group)}>✕</V2Button></div>{/each}<V2Button onclick={()=>addRule(group)}>+ Rule</V2Button></V2Stack></V2Card>{/each}</V2Stack></V2Section><V2Section title="Expression preview"><div class="v2-expression">{draftExpression}</div></V2Section></div><div class="v2-drawer-foot"><V2Badge text={`${draftRules.length+draftGroups.reduce((n,g)=>n+g.rules.length,0)} rules · ${draftGroups.length} groups`}/><V2Inline gap="sm"><V2Button onclick={resetDraft}>Reset</V2Button><V2Button onclick={()=>drawer=false}>Cancel</V2Button><V2Button variant="primary" onclick={applyDrawer}>Apply & Search</V2Button></V2Inline></div></aside>{/if}

<style>:global(.v2-selection-toolbar .v2-toolbar-group){flex-wrap:wrap}.v2-selection-more{position:relative}.v2-selection-menu{position:absolute;z-index:30;top:calc(100% + .4rem);right:0;min-width:14.5rem;display:grid;gap:.18rem;padding:.4rem;border:1px solid var(--v2-border,rgba(127,127,127,.32));border-radius:.65rem;background:var(--v2-surface,Canvas);box-shadow:0 .65rem 1.8rem rgba(0,0,0,.18)}.v2-selection-menu button{border:0;border-radius:.45rem;background:transparent;color:inherit;padding:.55rem .65rem;text-align:left;font:inherit;cursor:pointer;display:flex;align-items:center;gap:.6rem}.v2-selection-menu button:hover:not(:disabled){background:color-mix(in srgb,currentColor 8%,transparent)}.v2-selection-menu button:disabled{opacity:.42;cursor:not-allowed}.v2-selection-menu-separator{height:1px;background:var(--v2-border,rgba(127,127,127,.28));margin:.25rem 0}.v2-selection-menu-label{padding:.35rem .65rem .15rem;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;opacity:.62}</style>
