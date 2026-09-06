<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2DuplicateCompareViewer from '../components/V2DuplicateCompareViewer.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { demoCompareImage } from '../demo/duplicateVisuals';
  import { demoAssetState, initializeDemoAssetState, stackDemoAssets, trashDemoAssets } from '../demo/demoAssetState.svelte';

  type DuplicateTab='Review'|'Rules & discovery'|'Resolution history';
  const groupDefinitions=[
    {count:2,state:'Actionable',tone:'ok',kind:'Exact pair'},{count:2,state:'Needs review',tone:'warn',kind:'Similar pair'},{count:3,state:'Actionable',tone:'ok',kind:'Exact group'},
    {count:5,state:'Needs decisions',tone:'warn',kind:'Mixed group'},{count:6,state:'Actionable',tone:'ok',kind:'Similarity cluster'},{count:9,state:'Blocked',tone:'bad',kind:'Large cluster'},{count:10,state:'Needs review',tone:'warn',kind:'Large similarity cluster'},
  ] as const;
  let tab=$state<DuplicateTab>('Review'),compare=$state(false),group=$state(1),member=$state(0),reference=$state(0),decisions=$state<Record<string,string>>({}),selectedGroups=$state<number[]>([]),reviewFilter=$state('All groups');
  const sourceIds=$derived((demoAssetState.revision,demoAssetState.assets.slice(0,37).map((asset)=>asset.id)));
  const groups=$derived.by(()=>{let cursor=0;return groupDefinitions.map((definition,index)=>{const assetIds=sourceIds.slice(cursor,cursor+definition.count);cursor+=definition.count;return{id:index+1,...definition,assetIds}})});
  const visibleGroups=$derived(groups.filter((item)=>reviewFilter==='All groups'||item.state===reviewFilter||(reviewFilter==='Auto-ready'&&item.state==='Actionable')));
  const activeGroup=$derived(groups.find((item)=>item.id===group));
  const activeAssetIds=$derived(activeGroup?.assetIds??[]);
  const activeCount=$derived(activeAssetIds.length);
  const decisionCount=$derived(Object.keys(decisions).length);

  function openCompare(nextGroup:number,index:number){group=nextGroup;member=index;reference=0;compare=true}
  function setDecision(assetId:string,decision:string){decisions={...decisions,[assetId]:decision}}
  function presetGroup(item:(typeof groups)[number],decision:string){const next={...decisions};for(const id of item.assetIds)next[id]=decision;decisions=next}
  function applyBulkPreset(decision:string){const next={...decisions};for(const item of groups)if(selectedGroups.includes(item.id))for(const id of item.assetIds)next[id]=decision;decisions=next}
  function toggleGroup(id:number,checked:boolean){selectedGroups=checked?[...new Set([...selectedGroups,id])]:selectedGroups.filter((value)=>value!==id)}
  function executeDecisions(){const deleteIds=Object.entries(decisions).filter(([,decision])=>decision==='delete').map(([id])=>id);const stackIds=new Set(Object.entries(decisions).filter(([,decision])=>decision==='stack').map(([id])=>id));for(const item of groups){const members=item.assetIds.filter((id)=>stackIds.has(id));if(members.length>=2)stackDemoAssets(members)}if(deleteIds.length)trashDemoAssets(deleteIds);decisions={};selectedGroups=[];compare=false}

  onMount(()=>initializeDemoAssetState());
</script>

<V2PageLayout title="Duplicates" description="Review duplicate groups built from the same shared V2 demo assets used by Assets and Restore.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Scan similar</V2Button><V2Button variant="primary" disabled={decisionCount===0} onclick={executeDecisions}>Review actions{decisionCount?` (${decisionCount})`:''}</V2Button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Review','Rules & discovery','Resolution history']} active={tab} ariaLabel="Duplicate sections" onselect={(value)=>tab=value as DuplicateTab}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Review'}<V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-review-filter" label="Group state" bind:value={reviewFilter} options={['All groups','Needs review','Auto-ready','Blocked']}/><V2Button onclick={()=>selectedGroups=groups.filter((item)=>item.state==='Actionable').map((item)=>item.id)}>Select auto-ready</V2Button></V2Stack></V2Section><V2Section title="Similarity"><V2Field label="Threshold" value="82"/><span class="v2-small v2-muted">Similarity remains review evidence only.</span></V2Section><V2Section title="Bulk preset"><V2Stack gap="sm"><V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('keep')}>Keep all copies</V2Button><V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('delete')}>Mark all for deletion</V2Button><V2Button disabled={!selectedGroups.length} onclick={()=>applyBulkPreset('stack')}>Stack each group</V2Button></V2Stack></V2Section>{:else if tab==='Rules & discovery'}<V2Section title="Discovery"><V2Stack gap="sm"><V2Field label="Similarity threshold" value="82"/><V2Checkbox label="Include visually similar assets" checked={true}/><V2Checkbox label="Include exact file matches" checked={true}/><V2Button variant="primary">Run discovery</V2Button></V2Stack></V2Section>{:else}<V2Section title="History filter"><V2Stack gap="sm"><SelectField id="duplicate-history-range" label="Range" options={['Last 30 days','Last 90 days','All history']}/><V2Button>Export history</V2Button></V2Stack></V2Section>{/if}</V2Zone>{/snippet}

  <V2Zone>{#if tab==='Review'}<V2Toolbar><V2Badge text={`${visibleGroups.length} groups`}/><V2Badge tone="ok" text={`${groups.filter((item)=>item.state==='Actionable').length} ready`}/><V2Badge text={`${decisionCount} decisions`}/>{#snippet actions()}<V2Button onclick={()=>decisions={}}>Clear decisions</V2Button>{/snippet}</V2Toolbar>
    {#each visibleGroups as item}<V2Card class="v2-duplicate-group"><V2Stack gap="md"><V2Inline justify="between" align="start" wrap={true}><V2Inline gap="sm" wrap={true}><input type="checkbox" checked={selectedGroups.includes(item.id)} onchange={(event)=>toggleGroup(item.id,event.currentTarget.checked)}><b>Group {item.id}</b><V2Badge text={`${item.assetIds.length} images`}/><V2Badge text={item.kind}/><V2Badge tone={item.tone} text={item.state}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button onclick={()=>presetGroup(item,'keep')}>Keep preset</V2Button><V2Button onclick={()=>openCompare(item.id,0)}>Compare</V2Button></V2Inline></V2Inline><div class="v2-duplicate-members">
      {#each item.assetIds as assetId,index}{@const asset=demoAssetState.assets.find((candidate)=>candidate.id===assetId)}<div class="v2-duplicate-member"><button class="v2-duplicate-image" onclick={()=>openCompare(item.id,index)}><img src={demoCompareImage(item.id,index)} alt={asset?.original_file_name??`Duplicate member ${index+1}`}><span class="v2-duplicate-image-meta"><b>{asset?.original_file_name??`Member ${index+1}`}</b><small>{asset?.library_id?'External library':'Immich'}</small></span></button><div class="v2-duplicate-actions"><V2Button active={decisions[assetId]==='keep'} onclick={()=>setDecision(assetId,'keep')}>Keep</V2Button><V2Button active={decisions[assetId]==='delete'} onclick={()=>setDecision(assetId,'delete')}>Delete</V2Button><V2Button active={decisions[assetId]==='stack'} onclick={()=>setDecision(assetId,'stack')}>Stack</V2Button></div></div>{/each}
    </div></V2Stack></V2Card>{/each}
  {:else if tab==='Rules & discovery'}<V2Toolbar sticky={false}><b>Rules & discovery</b><V2Badge text="UI-only discovery configuration"/></V2Toolbar><div class="v2-setting-grid"><V2Card title="Exact matches"><V2Stack gap="sm"><V2Checkbox label="Detect identical file hashes" checked={true}/><V2Checkbox label="Group exact copies automatically" checked={true}/><V2Button>Save exact-match rules</V2Button></V2Stack></V2Card><V2Card title="Similarity discovery"><V2Stack gap="sm"><V2Field label="Minimum similarity" value="82"/><V2Field label="Maximum candidates per asset" value="20"/><V2Button variant="primary">Save discovery rules</V2Button></V2Stack></V2Card></div>
  {:else}<V2Toolbar sticky={false}><V2Badge text="Demo resolution history"/></V2Toolbar><V2Stack gap="sm">{#each [['Today 09:42','Group 1','Kept 1 · deleted 1'],['Yesterday 18:10','Group 3','Stacked 3 assets'],['Aug 30 14:22','Group 5','Reviewed · no action']] as row}<V2Card><V2Inline justify="between" wrap={true}><V2Stack gap="xs"><b>{row[1]}</b><span class="v2-small v2-muted">{row[0]}</span></V2Stack><span>{row[2]}</span></V2Inline></V2Card>{/each}</V2Stack>{/if}</V2Zone>
  {#snippet inspector()}<V2Zone>{#if tab==='Review'}<V2Section title="Batch readiness"><V2Card><V2Stack gap="sm"><b>{selectedGroups.length} selected groups</b><span class="v2-small v2-muted">Decisions reference real shared demo asset IDs; execution updates Assets/Restore.</span><V2Inline gap="sm"><V2Badge text={`${decisionCount} planned actions`}/></V2Inline></V2Stack></V2Card></V2Section>{:else if tab==='Rules & discovery'}<V2Section title="Discovery status"><V2Card><span class="v2-small v2-muted">Discovery configuration remains intentionally UI-only; review actions are wired to shared demo assets.</span></V2Card></V2Section>{/if}</V2Zone>{/snippet}
</V2PageLayout>

<V2DuplicateCompareViewer open={compare} {group} assetIds={activeAssetIds} bind:member bind:reference bind:decisions onclose={()=>compare=false}/>
