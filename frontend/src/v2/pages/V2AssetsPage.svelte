<script lang="ts">
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2ZoneLabel from '../components/V2ZoneLabel.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';

  type Rule = { id:number; field:string; op:string; value:string };
  type Group = { id:number; logic:'AND'|'OR'; negated:boolean; rules:Rule[] };
  let tab=$state('Browse'), searchMode=$state<'Simple'|'Expert'>('Simple'), page=$state(1), pageSize=$state(24), resultMode=$state<'Pagination'|'Infinite'>('Pagination'), loaded=$state(24), viewer=$state(false), drawer=$state(false), summary=$state('Simple search · current filters');
  const total=2418;
  let seq=$state(4), groupSeq=$state(2), logic=$state<'AND'|'OR'>('AND'), negated=$state(false), rules=$state<Rule[]>([{id:1,field:'mediaType',op:'is',value:'Image'},{id:2,field:'favorite',op:'is',value:'true'}]), groups=$state<Group[]>([{id:2,logic:'OR',negated:false,rules:[{id:3,field:'album',op:'is',value:'Family'},{id:4,field:'tag',op:'is',value:'Vacation'}]}]);
  let draftRules=$state<Rule[]>([]), draftGroups=$state<Group[]>([]), draftLogic=$state<'AND'|'OR'>('AND'), draftNegated=$state(false);
  const fields=['filename','mediaType','favorite','archived','album','tag','takenDate','width','height','aspectRatio'], ops=['is','isNot','contains','notContains','gt','gte','lt','lte'];
  const start=$derived((page-1)*pageSize), count=$derived(resultMode==='Pagination'?Math.min(pageSize,total-start):Math.min(loaded,total)), ids=$derived(Array.from({length:count},(_,i)=>resultMode==='Pagination'?start+i:i));
  const expression=$derived(expressionText(rules,groups,logic,negated));
  const draftExpression=$derived(expressionText(draftRules,draftGroups,draftLogic,draftNegated));

  function ruleText(r:Rule){return `${r.field} ${r.op} ${r.value||'…'}`}
  function expressionText(rs:Rule[],gs:Group[],root:'AND'|'OR',not:boolean){const base=`(${rs.map(ruleText).join(` ${root} `)||'empty'})`;const nested=gs.map(g=>`${g.negated?'NOT ':''}(${g.rules.map(ruleText).join(` ${g.logic} `)||'empty'})`);const text=[base,...nested].join(` ${root} `);return not?`NOT (${text})`:text}
  function setMode(mode:'Pagination'|'Infinite'){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function openDrawer(){draftRules=rules.map(r=>({...r}));draftGroups=groups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));draftLogic=logic;draftNegated=negated;drawer=true}
  function applyDrawer(){rules=draftRules.map(r=>({...r}));groups=draftGroups.map(g=>({...g,rules:g.rules.map(r=>({...r}))}));logic=draftLogic;negated=draftNegated;drawer=false;summary=`Expert search · ${expressionText(rules,groups,logic,negated)}`}
  function resetDraft(){draftRules=[];draftGroups=[];draftLogic='AND';draftNegated=false}
  function addRule(group?:Group){const rule={id:++seq,field:'filename',op:'contains',value:''};if(group)group.rules=[...group.rules,rule];else draftRules=[...draftRules,rule]}
  function removeRule(id:number,group?:Group){if(group)group.rules=group.rules.filter(r=>r.id!==id);else draftRules=draftRules.filter(r=>r.id!==id)}
  function addGroup(){draftGroups=[...draftGroups,{id:++groupSeq,logic:'AND',negated:false,rules:[{id:++seq,field:'tag',op:'is',value:''}]}]}
  function loadSaved(value:string){if(value.includes('Favorite')){rules=[{id:++seq,field:'mediaType',op:'is',value:'Image'},{id:++seq,field:'archived',op:'is',value:'false'},{id:++seq,field:'favorite',op:'is',value:'true'}];groups=[]}else if(value.includes('Family')){rules=[];groups=[{id:++groupSeq,logic:'OR',negated:false,rules:[{id:++seq,field:'album',op:'is',value:'Family'},{id:++seq,field:'tag',op:'is',value:'Vacation'}]}]}else if(value.includes('Large')){rules=[{id:++seq,field:'width',op:'gt',value:'3000'},{id:++seq,field:'aspectRatio',op:'gt',value:'1'}];groups=[]}summary='Expert draft · '+expressionText(rules,groups,logic,negated)}
</script>

<svelte:window onkeydown={(e)=>{if(e.key==='Escape'){if(drawer)drawer=false;else if(viewer)viewer=false}}}/>

<V2PageLayout title="Assets" description="Search, browse, select, synchronize and perform guarded actions on assets.">
  {#snippet headerActions()}<V2Inline gap="sm"><button class="v2-button">Sync selected</button><button class="v2-button v2-button-primary">Actions</button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Browse','Saved searches']} active={tab} onselect={(v)=>tab=v}/>{/snippet}
  {#snippet context()}<V2Zone label="Context rail"><V2Section title="Search mode"><V2Inline gap="sm"><button class={`v2-button ${searchMode==='Simple'?'v2-button-primary':''}`} onclick={()=>searchMode='Simple'}>Simple</button><button class={`v2-button ${searchMode==='Expert'?'v2-button-primary':''}`} onclick={()=>searchMode='Expert'}>Expert</button></V2Inline></V2Section>{#if searchMode==='Simple'}<V2Section title="Filters"><V2Stack gap="sm"><V2Field label="Filename" placeholder="Filename contains…"/><V2Field label="Media type" options={['Any','Image','Video']}/><V2Field label="Favorite" options={['Any','Favorite','Not favorite']}/><V2Field label="Archived" options={['Any','Archived','Not archived']}/><button class="v2-button">Advanced filters</button></V2Stack></V2Section>{:else}<V2Section title="Expert search"><V2Stack gap="sm"><V2Badge text="Boolean"/><V2Field label="Saved expert search" options={['Choose saved search…','Favorite images not archived','Family album or Vacation tag','Large landscape images']} onchange={loadSaved}/><V2Card><V2Stack gap="sm"><V2Inline justify="between"><b>Current expression</b><V2Badge text={`${rules.length+groups.reduce((n,g)=>n+g.rules.length,0)} rules · ${groups.length} groups`}/></V2Inline><span class="v2-small v2-muted">{expression}</span><button class="v2-button" onclick={openDrawer}>Edit expression</button></V2Stack></V2Card></V2Stack></V2Section>{/if}<V2Inline gap="sm"><button class="v2-button v2-button-primary" onclick={()=>summary=searchMode==='Expert'?`Expert search · ${expression}`:'Simple search · submitted filters'}>Search assets</button><button class="v2-button" onclick={()=>{summary=`${searchMode} search · cleared and reloaded`;if(searchMode==='Expert'){rules=[];groups=[]}}}>Clear</button></V2Inline></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content">
      <V2Badge text={`${total.toLocaleString()} matches`}/><button class="v2-button">Select loaded</button><button class="v2-button">Select all matching</button><button class="v2-button">Invert</button>
      {#snippet actions()}<select class="v2-select-auto"><option>Taken date ↓</option></select><select class="v2-select-auto" value={pageSize} onchange={(e)=>{pageSize=Number(e.currentTarget.value);page=1;loaded=pageSize}}><option value="24">24 / batch</option><option value="48">48 / batch</option><option value="96">96 / batch</option></select><div class="v2-segmented"><button class:active={resultMode==='Pagination'} onclick={()=>setMode('Pagination')}>Pagination</button><button class:active={resultMode==='Infinite'} onclick={()=>setMode('Infinite')}>Infinite</button></div>{/snippet}
    </V2Toolbar>
    <div class="v2-asset-grid">{#each ids as id}<V2AssetTile index={id} label={`IMG_${String(id+1).padStart(4,'0')}.jpg`} sublabel={`Aug ${21-(id%8)}, 2026`} onclick={()=>viewer=true}/>{/each}</div>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={(p)=>page=p}/>{:else}<div class="v2-infinite-sentinel"><div>{loaded>=total?`All ${total.toLocaleString()} matching assets loaded`:`${loaded.toLocaleString()} of ${total.toLocaleString()} loaded`}</div>{#if loaded<total}<button class="v2-button" onclick={()=>loaded=Math.min(total,loaded+pageSize)}>Load next {pageSize}</button>{/if}</div>{/if}
  </V2Zone>

  {#snippet inspector()}<V2Zone label="Inspector"><V2Section title="Active search"><V2Card><span class="v2-small">{summary}</span></V2Card></V2Section><V2Section title="Selection"><V2Card><V2Stack gap="sm"><b>3 assets selected</b><span class="v2-small v2-muted">Resolved selection summary and applicable actions.</span></V2Stack></V2Card></V2Section><V2Section title="Actions"><V2Stack gap="sm"><button class="v2-button">Add to album</button><button class="v2-button">Favorite</button><button class="v2-button">Archive</button><button class="v2-button">Stack</button><button class="v2-button">Add tags</button><button class="v2-button v2-button-danger">Move to trash</button></V2Stack></V2Section></V2Zone>{/snippet}
</V2PageLayout>

<V2Viewer open={viewer} title="Assets Viewer" mode="assets" onclose={()=>viewer=false}/>

{#if drawer}<div class="v2-drawer-backdrop" onclick={()=>drawer=false}></div><aside class="v2-drawer"><div class="v2-drawer-head"><div><V2ZoneLabel text="Expert search editor"/><h2>Build asset search expression</h2><p class="v2-muted">Edit the draft here. Results change only when you apply/search.</p></div><button class="v2-button" onclick={()=>drawer=false}>✕</button></div><div class="v2-drawer-body"><V2Section title="Expression structure"><V2Stack gap="md"><V2Card><V2Stack gap="sm"><V2Inline justify="between" wrap={true}><V2Inline gap="sm"><V2Badge text="Root group"/><div class="v2-segmented"><button class:active={draftLogic==='AND'} onclick={()=>draftLogic='AND'}>AND</button><button class:active={draftLogic==='OR'} onclick={()=>draftLogic='OR'}>OR</button></div><label class="v2-check-row"><input type="checkbox" bind:checked={draftNegated}>NOT group</label></V2Inline></V2Inline>{#each draftRules as rule}<div class="v2-expert-rule"><select bind:value={rule.field}>{#each fields as f}<option value={f}>{f}</option>{/each}</select><select bind:value={rule.op}>{#each ops as op}<option value={op}>{op}</option>{/each}</select><input bind:value={rule.value} placeholder="Value…"><button class="v2-button" onclick={()=>removeRule(rule.id)}>✕</button></div>{/each}<V2Inline gap="sm"><button class="v2-button" onclick={()=>addRule()}>+ Rule</button><button class="v2-button" onclick={addGroup}>+ Nested group</button></V2Inline></V2Stack></V2Card>{#each draftGroups as group}<V2Card><V2Stack gap="sm"><V2Inline justify="between"><V2Inline gap="sm"><V2Badge text="Nested group"/><div class="v2-segmented"><button class:active={group.logic==='AND'} onclick={()=>group.logic='AND'}>AND</button><button class:active={group.logic==='OR'} onclick={()=>group.logic='OR'}>OR</button></div><label class="v2-check-row"><input type="checkbox" bind:checked={group.negated}>NOT group</label></V2Inline><button class="v2-button" onclick={()=>draftGroups=draftGroups.filter(g=>g.id!==group.id)}>Remove group</button></V2Inline>{#each group.rules as rule}<div class="v2-expert-rule"><select bind:value={rule.field}>{#each fields as f}<option value={f}>{f}</option>{/each}</select><select bind:value={rule.op}>{#each ops as op}<option value={op}>{op}</option>{/each}</select><input bind:value={rule.value}><button class="v2-button" onclick={()=>removeRule(rule.id,group)}>✕</button></div>{/each}<button class="v2-button" onclick={()=>addRule(group)}>+ Rule</button></V2Stack></V2Card>{/each}</V2Stack></V2Section><V2Section title="Expression preview"><div class="v2-expression">{draftExpression}</div></V2Section></div><div class="v2-drawer-foot"><V2Badge text={`${draftRules.length+draftGroups.reduce((n,g)=>n+g.rules.length,0)} rules · ${draftGroups.length} groups`}/><V2Inline gap="sm"><button class="v2-button" onclick={resetDraft}>Reset</button><button class="v2-button" onclick={()=>drawer=false}>Cancel</button><button class="v2-button v2-button-primary" onclick={applyDrawer}>Apply & Search</button></V2Inline></div></aside>{/if}
