<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2ZoneLabel from '../components/V2ZoneLabel.svelte';

  type Rule = { id:number; field:string; op:string; value:string };
  type Group = { id:number; logic:'AND'|'OR'; negated:boolean; rules:Rule[] };
  const fieldOptions = [['filename','Filename'],['mediaType','Media type'],['favorite','Favorite'],['archived','Archived'],['album','Album'],['tag','Tag'],['takenDate','Taken date'],['width','Width'],['height','Height'],['aspectRatio','Aspect ratio']] as const;
  const operatorOptions = [['is','is'],['isNot','is not'],['contains','contains'],['notContains','does not contain'],['gt','greater than'],['gte','at least'],['lt','less than'],['lte','at most']] as const;
  const fieldSelectOptions = fieldOptions.map(([value,label]) => ({ value, label }));
  const operatorSelectOptions = operatorOptions.map(([value,label]) => ({ value, label }));

  let tab=$state('Browse'), searchMode=$state<'Simple'|'Expert'>('Simple'), page=$state(1), pageSize=$state(24), resultMode=$state<'Pagination'|'Infinite'>('Pagination'), loaded=$state(24), viewer=$state(false), drawer=$state(false), summary=$state('Simple search · current filters');
  let mediaType=$state(''), favorite=$state(''), archived=$state('');
  const total=2418;
  let seq=$state(4), groupSeq=$state(2), logic=$state<'AND'|'OR'>('AND'), negated=$state(false), rules=$state<Rule[]>([{id:1,field:'mediaType',op:'is',value:'Image'},{id:2,field:'favorite',op:'is',value:'true'}]), groups=$state<Group[]>([{id:2,logic:'OR',negated:false,rules:[{id:3,field:'album',op:'is',value:'Family'},{id:4,field:'tag',op:'is',value:'Vacation'}]}]);
  let draftRules=$state<Rule[]>([]), draftGroups=$state<Group[]>([]), draftLogic=$state<'AND'|'OR'>('AND'), draftNegated=$state(false);
  const start=$derived((page-1)*pageSize), count=$derived(resultMode==='Pagination'?Math.min(pageSize,total-start):Math.min(loaded,total)), ids=$derived(Array.from({length:count},(_,i)=>resultMode==='Pagination'?start+i:i));
  const expression=$derived(expressionText(rules,groups,logic,negated));
  const draftExpression=$derived(expressionText(draftRules,draftGroups,draftLogic,draftNegated));

  const fieldLabel=(value:string)=>fieldOptions.find(([key])=>key===value)?.[1]??value;
  const operatorLabel=(value:string)=>operatorOptions.find(([key])=>key===value)?.[1]??value;
  function ruleText(r:Rule){return `${fieldLabel(r.field)} ${operatorLabel(r.op)} ${r.value||'…'}`}
  function expressionText(rs:Rule[],gs:Group[],root:'AND'|'OR',not:boolean){const base=`(${rs.map(ruleText).join(` ${root} `)||'empty'})`;const nested=gs.map(g=>`${g.negated?'NOT ':''}(${g.rules.map(ruleText).join(` ${g.logic} `)||'empty'})`);const text=[base,...nested].join(` ${root} `);return not?`NOT (${text})`:text}
  function scrollResultsTop(){document.querySelector<HTMLElement>('.v2-content')?.scrollTo({top:0,behavior:'smooth'})}
  function setPage(next:number){page=next;scrollResultsTop()}
  function setMode(mode:'Pagination'|'Infinite'){resultMode=mode;localStorage.setItem('immichCompanionResultMode',mode==='Pagination'?'paged':'infinite');if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function setPageSize(next:number){pageSize=next;page=1;loaded=next}
  function openDrawer(){draftRules=rules.map(r=>({...r}));draftGroups=groups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));draftLogic=logic;draftNegated=negated;drawer=true}
  function applyDrawer(){rules=draftRules.map(r=>({...r}));groups=draftGroups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));logic=draftLogic;negated=draftNegated;drawer=false;summary=`Expert search · ${expressionText(rules,groups,logic,negated)}`}
  function resetDraft(){draftRules=[];draftGroups=[];draftLogic='AND';draftNegated=false}
  function addRule(group?:Group){const rule={id:++seq,field:'filename',op:'contains',value:''};if(group)group.rules=[...group.rules,rule];else draftRules=[...draftRules,rule]}
  function removeRule(id:number,group?:Group){if(group)group.rules=group.rules.filter(r=>r.id!==id);else draftRules=draftRules.filter(r=>r.id!==id)}
  function addGroup(){draftGroups=[...draftGroups,{id:++groupSeq,logic:'AND',negated:false,rules:[{id:++seq,field:'tag',op:'is',value:''}]}]}
  function loadSaved(value:string){
    if(value.includes('Favorite')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'},{id:++seq,field:'favorite',op:'is',value:'true'},{id:++seq,field:'archived',op:'is',value:'false'}];groups=[]}
    else if(value.includes('Family')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'}];groups=[{id:++groupSeq,logic:'OR',negated:false,rules:[{id:++seq,field:'album',op:'is',value:'Family'},{id:++seq,field:'tag',op:'is',value:'Vacation'}]}]}
    else if(value.includes('Large')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'},{id:++seq,field:'width',op:'gte',value:'3000'},{id:++seq,field:'aspectRatio',op:'gt',value:'1'}];groups=[]}
    summary='Expert draft · '+expressionText(rules,groups,logic,negated);
  }

  onMount(()=>{const stored=localStorage.getItem('immichCompanionResultMode');if(stored==='infinite'){resultMode='Infinite';loaded=Math.max(pageSize,loaded)}});
</script>

<svelte:window onkeydown={(e)=>{if(e.key==='Escape'){if(drawer)drawer=false;else if(viewer)viewer=false}}}/>

<V2PageLayout title="Assets" description="Search, browse, select, synchronize and perform guarded actions on assets.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Sync selected</V2Button><V2Button variant="primary">Actions</V2Button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Browse','Saved searches']} active={tab} onselect={(value)=>tab=value}/>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search mode"><V2Segmented items={['Simple','Expert']} active={searchMode} onselect={(value)=>searchMode=value as 'Simple'|'Expert'} ariaLabel="Search mode" /></V2Section>{#if searchMode==='Simple'}<V2Section title="Filters"><V2Stack gap="sm"><V2Field label="Filename" placeholder="Filename contains…"/><SelectField id="asset-media-type" label="Media type" allowEmpty={true} placeholder="Any" bind:value={mediaType} options={['Image','Video']}/><SelectField id="asset-favorite" label="Favorite" allowEmpty={true} placeholder="Any" bind:value={favorite} options={['Favorite','Not favorite']}/><SelectField id="asset-archived" label="Archived" allowEmpty={true} placeholder="Any" bind:value={archived} options={['Archived','Not archived']}/><V2Button>Advanced filters</V2Button></V2Stack></V2Section>{:else}<V2Section title="Expert search">{#snippet actions()}<V2Badge text="Boolean"/>{/snippet}<V2Stack gap="sm"><SelectField id="asset-saved-search" label="Saved expert search" allowEmpty={true} placeholder="Choose saved search…" options={['Favorite images not archived','Family album or Vacation tag','Large landscape images']} onchange={loadSaved}/><V2Card><V2Stack gap="sm"><V2Inline justify="between"><b>Current expression</b><V2Badge text={`${rules.length+groups.reduce((n,g)=>n+g.rules.length,0)} rules · ${groups.length} groups`}/></V2Inline><span class="v2-small v2-muted">{expression}</span><V2Button block={true} onclick={openDrawer}>Edit expression</V2Button></V2Stack></V2Card></V2Stack></V2Section>{/if}<V2Inline gap="sm"><V2Button variant="primary" onclick={()=>summary=searchMode==='Expert'?`Expert search · ${expression}`:'Simple search · submitted filters'}>Search assets</V2Button><V2Button onclick={()=>{summary=`${searchMode} search · cleared and reloaded`;mediaType='';favorite='';archived='';if(searchMode==='Expert'){rules=[];groups=[]}}}>Clear</V2Button></V2Inline></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text={`${total.toLocaleString()} matches`}/><V2Button>Select loaded</V2Button><V2Button>Select all matching</V2Button><V2Button>Invert</V2Button>
      {#snippet actions()}<SelectField id="asset-sort" width="content" options={['Taken date ↓']}/><SelectField id="asset-page-size" width="content" value={pageSize} options={[{value:'24',label:'24 / batch'},{value:'48',label:'48 / batch'},{value:'96',label:'96 / batch'}]} onchange={(value)=>setPageSize(Number(value))}/><V2Segmented items={['Pagination','Infinite']} active={resultMode} onselect={(value)=>setMode(value as 'Pagination'|'Infinite')} ariaLabel="Result loading mode" />{/snippet}
    </V2Toolbar>
    <div class="v2-asset-grid">{#each ids as id}<V2AssetTile index={id} label={`IMG_${String(id+1).padStart(4,'0')}.jpg`} sublabel={`Aug ${21-(id%8)}, 2026`} onclick={()=>viewer=true}/>{/each}</div>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={setPage}/>{:else}<div class="v2-infinite-sentinel" data-loading={loaded<total || undefined}><div>{loaded>=total?`All ${total.toLocaleString()} matching assets loaded`:`${loaded.toLocaleString()} of ${total.toLocaleString()} loaded`}</div>{#if loaded<total}<V2Button onclick={()=>loaded=Math.min(total,loaded+pageSize)}>Load next {pageSize}</V2Button>{/if}</div>{/if}
  </V2Zone>

  {#snippet inspector()}<V2Zone><V2Section title="Active search"><V2Card><span class="v2-small">{summary}</span></V2Card></V2Section><V2Section title="Selection"><V2Card><V2Stack gap="sm"><b>3 assets selected</b><span class="v2-small v2-muted">Resolved selection summary and applicable actions.</span></V2Stack></V2Card></V2Section><V2Section title="Actions"><V2Stack gap="sm"><V2Button>Add to album</V2Button><V2Button>Favorite</V2Button><V2Button>Archive</V2Button><V2Button>Stack</V2Button><V2Button>Add tags</V2Button><V2Button variant="danger">Move to trash</V2Button></V2Stack></V2Section></V2Zone>{/snippet}
</V2PageLayout>

<V2Viewer open={viewer} title="Assets Viewer" mode="assets" onclose={()=>viewer=false}/>

{#if drawer}<div class="v2-drawer-backdrop" onclick={()=>drawer=false}></div><aside class="v2-drawer"><div class="v2-drawer-head"><div><V2ZoneLabel text="Expert search editor"/><h2>Build asset search expression</h2><p class="v2-muted">Edit the draft here. Results change only when you apply/search.</p></div><V2Button onclick={()=>drawer=false}>✕</V2Button></div><div class="v2-drawer-body"><V2Section title="Expression structure"><V2Stack gap="md"><V2Card><V2Stack gap="sm"><V2Inline justify="between" wrap={true}><V2Inline gap="sm"><V2Badge text="Root group"/><V2Segmented items={['AND','OR']} active={draftLogic} onselect={(value)=>draftLogic=value as 'AND'|'OR'} ariaLabel="Root group logic"/><V2Checkbox label="NOT group" checked={draftNegated} onchange={(checked)=>draftNegated=checked}/></V2Inline></V2Inline>{#each draftRules as rule}<div class="v2-expert-rule"><SelectField id={`expert-root-field-${rule.id}`} value={rule.field} options={fieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-root-op-${rule.id}`} value={rule.op} options={operatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value} placeholder="Value…"><V2Button onclick={()=>removeRule(rule.id)}>✕</V2Button></div>{/each}<V2Inline gap="sm"><V2Button onclick={()=>addRule()}>+ Rule</V2Button><V2Button onclick={addGroup}>+ Nested group</V2Button></V2Inline></V2Stack></V2Card>{#each draftGroups as group}<V2Card><V2Stack gap="sm"><V2Inline justify="between"><V2Inline gap="sm"><V2Badge text="Nested group"/><V2Segmented items={['AND','OR']} active={group.logic} onselect={(value)=>group.logic=value as 'AND'|'OR'} ariaLabel="Nested group logic"/><V2Checkbox label="NOT group" checked={group.negated} onchange={(checked)=>group.negated=checked}/></V2Inline><V2Button onclick={()=>draftGroups=draftGroups.filter(g=>g.id!==group.id)}>Remove group</V2Button></V2Inline>{#each group.rules as rule}<div class="v2-expert-rule"><SelectField id={`expert-group-${group.id}-field-${rule.id}`} value={rule.field} options={fieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-group-${group.id}-op-${rule.id}`} value={rule.op} options={operatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value}><V2Button onclick={()=>removeRule(rule.id,group)}>✕</V2Button></div>{/each}<V2Button onclick={()=>addRule(group)}>+ Rule</V2Button></V2Stack></V2Card>{/each}</V2Stack></V2Section><V2Section title="Expression preview"><div class="v2-expression">{draftExpression}</div></V2Section></div><div class="v2-drawer-foot"><V2Badge text={`${draftRules.length+draftGroups.reduce((n,g)=>n+g.rules.length,0)} rules · ${draftGroups.length} groups`}/><V2Inline gap="sm"><V2Button onclick={resetDraft}>Reset</V2Button><V2Button onclick={()=>drawer=false}>Cancel</V2Button><V2Button variant="primary" onclick={applyDrawer}>Apply & Search</V2Button></V2Inline></div></aside>{/if}
