<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2CollectionFooter from '../components/V2CollectionFooter.svelte';
  import V2DuplicateCompareViewer from '../components/V2DuplicateCompareViewer.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createCollectionView } from '../state/collectionView.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { DuplicateCapabilities, DuplicateDecision, DuplicateGroupRecord, DuplicateHistoryRecord, DuplicateState } from '../data/contracts';

  type DuplicateTab='Review'|'Rules & discovery'|'Resolution history';
  const collection=createCollectionView({pageSize:6,resultModeStorageKey:'immichCompanionDuplicateResultMode'});
  let tab=$state<DuplicateTab>('Review'),compare=$state(false),group=$state(1),member=$state(0),reference=$state(0);
  let decisions=$state<Record<string,DuplicateDecision>>({}),selectedGroups=$state<number[]>([]),reviewFilter=$state<DuplicateState|'All groups'|'Auto-ready'>('All groups');
  let groups=$state<DuplicateGroupRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),loading=$state(false);
  let capabilities=$state<DuplicateCapabilities>({canRunDiscovery:false,canApplyDecisions:false,canViewHistory:false,reviewFilters:['All groups'],decisions:[]});
  let similarityThreshold=$state('82'),includeSimilar=$state(true),includeExact=$state(true),maxCandidates=$state('20'),discoverySummary=$state('');
  let historyRange=$state<'Last 30 days'|'Last 90 days'|'All history'>('Last 30 days'),history=$state<DuplicateHistoryRecord[]>([]);

  const activeGroup=$derived(groups.find((item)=>item.id===group)),activeAssetIds=$derived(activeGroup?.members.map((item)=>item.asset.id)??[]),decisionCount=$derived(Object.keys(decisions).length);
  const reviewFilterOptions=$derived(capabilities.reviewFilters.map(String));

  async function refreshGroups(reset=true){if(loading)return;loading=true;try{if(reset){nextCursor=null;if(collection.resultMode==='Infinite')collection.reset()}const query=collection.resultMode==='Pagination'?{state:reviewFilter,page:collection.page,pageSize:collection.pageSize}:{state:reviewFilter,pageSize:collection.pageSize,cursor:reset?null:nextCursor};const result=await libraryData.duplicates.search(query);groups=collection.resultMode==='Infinite'&&!reset?[...groups,...result.items]:result.items;total=result.total;nextCursor=result.nextCursor;collection.clampPage(total)}finally{loading=false}}
  async function loadMore(){if(!nextCursor||loading)return;collection.loadMore(total);await refreshGroups(false)}
  function setPage(value:number){collection.setPage(value);void refreshGroups()}
  function setPageSize(value:number){collection.setPageSize(value,total);void refreshGroups()}
  function setMode(value:ResultMode){collection.setMode(value);void refreshGroups()}
  function setReviewFilter(value:string){reviewFilter=value as typeof reviewFilter;collection.reset();selectedGroups=[];void refreshGroups()}
  function openCompare(nextGroup:number,index:number){group=nextGroup;member=index;reference=0;compare=true}
  function setDecision(assetId:string,decision:DuplicateDecision){if(capabilities.decisions.includes(decision))decisions={...decisions,[assetId]:decision}}
  function presetGroup(item:DuplicateGroupRecord,decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const next={...decisions};for(const member of item.members)next[member.asset.id]=decision;decisions=next}
  function applyBulkPreset(decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const next={...decisions};for(const item of groups)if(selectedGroups.includes(item.id))for(const member of item.members)next[member.asset.id]=decision;decisions=next}
  function toggleGroup(id:number,checked:boolean){selectedGroups=checked?[...new Set([...selectedGroups,id])]:selectedGroups.filter((value)=>value!==id)}
  async function executeDecisions(){if(!capabilities.canApplyDecisions||decisionCount===0)return;await libraryData.duplicates.applyDecisions(decisions);decisions={};selectedGroups=[];compare=false;await refreshGroups()}
  async function runDiscovery(){if(!capabilities.canRunDiscovery)return;const result=await libraryData.duplicates.runDiscovery({similarityThreshold:Number(similarityThreshold)||0,includeSimilar,includeExact,maxCandidates:Math.max(1,Number(maxCandidates)||20)});discoverySummary=`${result.groupCount} groups · ${result.candidateCount} candidates`;await refreshGroups()}
  async function refreshHistory(){if(!capabilities.canViewHistory){history=[];return}const result=await libraryData.duplicates.history({range:historyRange,page:1,pageSize:50});history=result.items}

  onMount(()=>{void(async()=>{await libraryData.initialize();collection.hydrate();capabilities=await libraryData.duplicates.capabilities();if(!capabilities.reviewFilters.includes(reviewFilter))reviewFilter=capabilities.reviewFilters[0]??'All groups';await Promise.all([refreshGroups(),refreshHistory()])})()});
</script>

<V2PageLayout title="Duplicates" description="Review duplicate groups supplied by the active data source, with provider-backed discovery and decisions.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!capabilities.canRunDiscovery||loading} onclick={runDiscovery}>Scan similar</V2Button><V2Button variant="primary" disabled={!capabilities.canApplyDecisions||decisionCount===0} onclick={executeDecisions}>Review actions{decisionCount?` (${decisionCount})`:''}</V2Button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Review','Rules & discovery','Resolution history']} active={tab} ariaLabel="Duplicate sections" onselect={(value)=>{tab=value as DuplicateTab;if(tab==='Resolution history')void refreshHistory()}}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Review'}<V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-review-filter" label="Group state" value={reviewFilter} options={reviewFilterOptions} onchange={setReviewFilter}/><V2Button disabled={!groups.some((item)=>item.state==='Actionable')} onclick={()=>selectedGroups=groups.filter((item)=>item.state==='Actionable').map((item)=>item.id)}>Select auto-ready</V2Button></V2Stack></V2Section><V2Section title="Similarity"><V2Field label="Threshold" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><span class="v2-small v2-muted">Similarity remains review evidence only.</span></V2Section><V2Section title="Bulk preset"><V2Stack gap="sm">{#if capabilities.decisions.includes('keep')}<V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('keep')}>Keep all copies</V2Button>{/if}{#if capabilities.decisions.includes('delete')}<V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('delete')}>Mark all for deletion</V2Button>{/if}{#if capabilities.decisions.includes('stack')}<V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('stack')}>Stack each group</V2Button>{/if}</V2Stack></V2Section>{:else if tab==='Rules & discovery'}<V2Section title="Discovery"><V2Stack gap="sm"><V2Field label="Similarity threshold" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><V2Checkbox label="Include visually similar assets" checked={includeSimilar} onchange={(checked)=>includeSimilar=checked}/><V2Checkbox label="Include exact file matches" checked={includeExact} onchange={(checked)=>includeExact=checked}/><V2Field label="Maximum candidates per asset" value={maxCandidates} onchange={(value)=>maxCandidates=value}/><V2Button variant="primary" disabled={!capabilities.canRunDiscovery} onclick={runDiscovery}>Run discovery</V2Button>{#if discoverySummary}<span class="v2-small v2-muted">{discoverySummary}</span>{/if}</V2Stack></V2Section>{:else}<V2Section title="History filter"><V2Stack gap="sm"><SelectField id="duplicate-history-range" label="Range" value={historyRange} options={['Last 30 days','Last 90 days','All history']} onchange={(value)=>{historyRange=value as typeof historyRange;void refreshHistory()}}/><V2Button disabled={!capabilities.canViewHistory} onclick={refreshHistory}>Refresh history</V2Button></V2Stack></V2Section>{/if}</V2Zone>{/snippet}

  <V2Zone>{#if tab==='Review'}<V2Toolbar><V2Badge text={`${total} groups`}/><V2Badge tone="ok" text={`${groups.filter((item)=>item.state==='Actionable').length} loaded ready`}/><V2Badge text={`${decisionCount} decisions`}/>{#snippet actions()}<V2CollectionControls id="duplicate-results" sort="state:asc" sortFields={[]} pageSize={collection.pageSize} pageSizes={[6,12,24]} resultMode={collection.resultMode} onsort={()=>{}} onpagesize={setPageSize} onmode={setMode}/><V2Button onclick={()=>decisions={}}>Clear decisions</V2Button>{/snippet}</V2Toolbar>
    {#each groups as item}<V2Card class="v2-duplicate-group"><V2Stack gap="md"><V2Inline justify="between" align="start" wrap={true}><V2Inline gap="sm" wrap={true}><input type="checkbox" checked={selectedGroups.includes(item.id)} onchange={(event)=>toggleGroup(item.id,event.currentTarget.checked)}><b>Group {item.id}</b><V2Badge text={`${item.members.length} images`}/><V2Badge text={item.kind}/><V2Badge tone={item.state==='Actionable'?'ok':item.state==='Blocked'?'bad':'warn'} text={item.state}/></V2Inline><V2Inline gap="sm" wrap={true}>{#if capabilities.decisions.includes('keep')}<V2Button onclick={()=>presetGroup(item,'keep')}>Keep preset</V2Button>{/if}<V2Button onclick={()=>openCompare(item.id,0)}>Compare</V2Button></V2Inline></V2Inline><div class="v2-duplicate-members">
      {#each item.members as member,index}<div class="v2-duplicate-member"><button class="v2-duplicate-image" onclick={()=>openCompare(item.id,index)}><img src={libraryData.media.thumbnail(member.asset).url} alt={member.asset.original_file_name} loading="lazy" decoding="async"><span class="v2-duplicate-image-meta"><b>{member.asset.original_file_name}</b><small>{member.asset.library_id?'External library':'Immich'} · {member.similarity.toFixed(1)}%</small></span></button><div class="v2-duplicate-actions">{#each capabilities.decisions as decision}<V2Button active={decisions[member.asset.id]===decision} onclick={()=>setDecision(member.asset.id,decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</div></div>{/each}
    </div></V2Stack></V2Card>{/each}
    {#if total>0}<V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={groups.length} noun="groups" onpage={setPage} onloadmore={loadMore}/>{/if}
  {:else if tab==='Rules & discovery'}<V2Toolbar sticky={false}><b>Rules & discovery</b><V2Badge text={capabilities.canRunDiscovery?'Provider-backed':'Unavailable'}/></V2Toolbar><div class="v2-setting-grid"><V2Card title="Exact matches"><V2Stack gap="sm"><V2Checkbox label="Detect identical file hashes" checked={includeExact} onchange={(checked)=>includeExact=checked}/><V2Button disabled={!capabilities.canRunDiscovery} onclick={runDiscovery}>Apply & scan</V2Button></V2Stack></V2Card><V2Card title="Similarity discovery"><V2Stack gap="sm"><V2Field label="Minimum similarity" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><V2Field label="Maximum candidates per asset" value={maxCandidates} onchange={(value)=>maxCandidates=value}/><V2Button variant="primary" disabled={!capabilities.canRunDiscovery} onclick={runDiscovery}>Run discovery</V2Button></V2Stack></V2Card></div>
  {:else}<V2Toolbar sticky={false}><V2Badge text="Resolution history"/></V2Toolbar><V2Stack gap="sm">{#each history as row}<V2Card><V2Inline justify="between" wrap={true}><V2Stack gap="xs"><b>{row.groupLabel}</b><span class="v2-small v2-muted">{new Date(row.occurredAt).toLocaleString()}</span></V2Stack><span>{row.summary}</span></V2Inline></V2Card>{:else}<V2Card><span class="v2-muted">No resolution history in this range.</span></V2Card>{/each}</V2Stack>{/if}</V2Zone>
</V2PageLayout>

<V2DuplicateCompareViewer open={compare} {group} assetIds={activeAssetIds} bind:member bind:reference bind:decisions onclose={()=>compare=false}/>
