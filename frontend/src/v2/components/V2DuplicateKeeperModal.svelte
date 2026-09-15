<script lang="ts">
  import { ArrowDown, ArrowUp, Plus, Trash2 } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import SelectField, { type SelectOption } from './SelectField.svelte';
  import DateTimePickerField from './DateTimePickerField.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Field from './V2Field.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2Stack from './V2Stack.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type {
    DuplicateKeeperRuleField,
    DuplicateKeeperSelectionResult,
    DuplicateSourceFilter,
    DuplicateState,
  } from '../data/contracts';
  import {
    keeperEffectOptions,
    keeperFieldDefinition,
    keeperOperatorOptions,
    keeperPreset,
    keeperPresetNames,
    keeperRuleFieldOptions,
    keeperRuleNeedsValue,
    newKeeperRule,
    normalizeKeeperRule,
    type DuplicateKeeperUiRule,
    type KeeperPresetName,
  } from '../state/duplicateKeeperRules';

  let {
    groupIds,
    initialScope = 'current_page',
    reviewFilter,
    sourceFilter,
    onclose,
    onapplied,
  }: {
    groupIds: string[];
    initialScope?: 'current_page'|'all_matching';
    reviewFilter: DuplicateState|'All groups'|'Auto-ready'|'Selected';
    sourceFilter: DuplicateSourceFilter;
    onclose: () => void;
    onapplied?: (result: DuplicateKeeperSelectionResult) => void;
  } = $props();

  let nextId=1;
  const newId=()=>nextId++;
  let scope=$state<'current_page'|'all_matching'>('current_page');
  $effect(()=>{ scope=initialScope; });
  let preset=$state<KeeperPresetName>('Highest quality');
  let rules=$state<DuplicateKeeperUiRule[]>(keeperPreset('Highest quality',newId));
  let overwriteManual=$state(false);
  let preview=$state<DuplicateKeeperSelectionResult|null>(null);
  let busy=$state(false),error=$state('');
  let albumOptions=$state<SelectOption[]>([]),tagOptions=$state<SelectOption[]>([]);
  let albumLoading=$state(false),tagLoading=$state(false);

  const validRules=$derived(rules.map(normalizeKeeperRule).filter((rule)=>!keeperRuleNeedsValue(rule)||rule.value.trim().length>0));
  const canRun=$derived(validRules.length>0&&!busy&&(scope==='all_matching'||groupIds.length>0));

  function markDirty(){preview=null;error=''}
  function updateRule(id:number,patch:Partial<DuplicateKeeperUiRule>){
    rules=rules.map((rule)=>{
      if(rule.id!==id)return rule;
      const next={...rule,...patch};
      if(patch.field||patch.effect){
        const operators=keeperOperatorOptions(next.field,next.effect);
        if(!operators.some((item)=>item.value===next.operator)){
          next.operator=(operators[0]?.value??'is') as DuplicateKeeperUiRule['operator'];
          next.value='';
        }
      }
      if(patch.operator&&!keeperRuleNeedsValue(next))next.value='';
      return next;
    });
    markDirty();
  }
  function addRule(){rules=[...rules,newKeeperRule(newId())];preset='Highest quality';markDirty()}
  function removeRule(id:number){rules=rules.filter((rule)=>rule.id!==id);markDirty()}
  function moveRule(index:number,direction:-1|1){
    const target=index+direction;
    if(target<0||target>=rules.length)return;
    const copy=[...rules];
    [copy[index],copy[target]]=[copy[target],copy[index]];
    rules=copy;markDirty();
  }
  function applyPreset(value:string){
    preset=value as KeeperPresetName;
    rules=keeperPreset(preset,newId);
    markDirty();
  }
  async function loadOptions(kind:'album'|'tag',query=''){
    const loading=kind==='album'?()=>albumLoading=true:()=>tagLoading=true;
    loading();
    try{
      const result=kind==='album'
        ?await libraryData.albums.searchOptions({query,pageSize:50})
        :await libraryData.tags.searchOptions({query,pageSize:50});
      const options=result.items.map((item)=>({value:item.value,label:item.label,subtitle:item.subtitle}));
      if(kind==='album')albumOptions=options;else tagOptions=options;
    }finally{
      if(kind==='album')albumLoading=false;else tagLoading=false;
    }
  }
  function relationValues(rule:DuplicateKeeperUiRule){return rule.value.split(',').map((part)=>part.trim()).filter(Boolean)}
  function setRelationValues(rule:DuplicateKeeperUiRule,values:string[]){updateRule(rule.id,{value:values.join(',')})}
  function inputType(field:DuplicateKeeperRuleField){return keeperFieldDefinition(field).kind==='number'?'number':'text'}
  function placeholder(field:DuplicateKeeperRuleField){
    if(field==='library')return 'upload or library UUID';
    if(field==='folder')return '/photos/originals';
    if(field==='extension')return 'dng, heic, jpg…';
    if(field==='mime_type')return 'image/jpeg';
    if(field==='owner')return 'Owner UUID';
    if(field==='visibility')return 'timeline';
    return 'Value';
  }
  function requestPayload(){
    return{scope,groupIds,reviewFilter,sourceFilter,rules:validRules,overwriteManual};
  }
  async function runPreview(){
    if(!canRun)return;
    busy=true;error='';
    try{preview=await libraryData.duplicates.previewKeeperRules(requestPayload())}
    catch(reason){error=reason instanceof Error?reason.message:'Keeper rule preview failed.'}
    finally{busy=false}
  }
  async function applyRules(){
    if(!canRun)return;
    busy=true;error='';
    try{
      const result=await libraryData.duplicates.applyKeeperRules(requestPayload());
      preview=result;
      onapplied?.(result);
    }catch(reason){error=reason instanceof Error?reason.message:'Keeper rules could not be applied.'}
    finally{busy=false}
  }
  onMount(()=>{void Promise.all([loadOptions('album'),loadOptions('tag')])});
</script>

<V2Modal
  id="duplicate-keeper-rules"
  title="Auto-select keeper"
  description="Choose one keeper per valid duplicate group. The other members are saved as Delete drafts; nothing is trashed until you review and execute those drafts. Keeper rules choose a single winner; group-level Keep all policies are separate decisions."
  size="xl"
  onclose={onclose}
>
  <V2Stack gap="md">
    <V2Card>
      <V2Stack gap="sm">
        <div class="keeper-grid keeper-grid--scope">
          <SelectField id="keeper-preset" label="Quick preset" value={preset} options={keeperPresetNames.map((value)=>({value,label:value}))} onchange={applyPreset}/>
          <div>
            <span class="v2-field-label">Scope</span>
            <V2Segmented
              items={[{value:'current_page',label:`Current page · ${groupIds.length} loaded`},{value:'all_matching',label:'All groups matching filters'}]}
              active={scope}
              ariaLabel="Keeper rule scope"
              onselect={(value)=>{scope=value as typeof scope;markDirty()}}
            />
          </div>
        </div>
        <span class="v2-small v2-muted">Current page only evaluates the groups loaded in the review list. All groups matching filters evaluates the full result set for the current discovery source and group-state filter, including groups on other pages.</span>
        <V2Inline gap="md" wrap>
          <V2Badge>State: {reviewFilter}</V2Badge>
          <V2Badge>Source: {sourceFilter}</V2Badge>
          <V2Checkbox label="Replace existing manual choices" checked={overwriteManual} onchange={(value)=>{overwriteManual=value;markDirty()}}/>
        </V2Inline>
      </V2Stack>
    </V2Card>

    <div class="keeper-rules-heading">
      <div>
        <h3>Keeper priority</h3>
        <p>Require rules filter candidates first. Prefer and Avoid rules are then evaluated from top to bottom. If a tie remains, the current reference wins; otherwise the group is skipped.</p>
      </div>
      <V2Button onclick={addRule}><Plus size={15}/> Add condition</V2Button>
    </div>

    <div class="keeper-rule-list">
      {#each rules as rule,index (rule.id)}
        {@const definition=keeperFieldDefinition(rule.field)}
        {@const operators=keeperOperatorOptions(rule.field,rule.effect)}
        <V2Card>
          <div class="keeper-rule-row">
            <div class="keeper-rule-order">
              <V2Button iconOnly ariaLabel="Move condition up" disabled={index===0} onclick={()=>moveRule(index,-1)}><ArrowUp size={15}/></V2Button>
              <span>{index+1}</span>
              <V2Button iconOnly ariaLabel="Move condition down" disabled={index===rules.length-1} onclick={()=>moveRule(index,1)}><ArrowDown size={15}/></V2Button>
            </div>
            <SelectField
              id={`keeper-effect-${rule.id}`}
              label="Behavior"
              value={rule.effect}
              options={keeperEffectOptions}
              onchange={(value)=>updateRule(rule.id,{effect:value as DuplicateKeeperUiRule['effect']})}
            />
            <SelectField
              id={`keeper-field-${rule.id}`}
              label="Condition"
              value={rule.field}
              options={keeperRuleFieldOptions}
              searchable
              onchange={(value)=>updateRule(rule.id,{field:value as DuplicateKeeperRuleField})}
            />
            <SelectField
              id={`keeper-operator-${rule.id}`}
              label="Match"
              value={rule.operator}
              options={[...operators]}
              onchange={(value)=>updateRule(rule.id,{operator:value as DuplicateKeeperUiRule['operator']})}
            />
            <div class="keeper-rule-value">
              {#if keeperRuleNeedsValue(rule)}
                {#if definition.kind==='media'}
                  <SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateRule(rule.id,{value})}/>
                {:else if definition.kind==='availability'}
                  <SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value)=>updateRule(rule.id,{value})}/>
                {:else if definition.kind==='date'}
                  <DateTimePickerField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} showTime onchange={(value)=>updateRule(rule.id,{value})}/>
                {:else if definition.kind==='relation'}
                  <SelectField
                    id={`keeper-value-${rule.id}`}
                    label="Value"
                    multiple
                    values={relationValues(rule)}
                    options={rule.field==='album'?albumOptions:tagOptions}
                    searchable
                    loading={rule.field==='album'?albumLoading:tagLoading}
                    searchPlaceholder={`Search ${rule.field}s…`}
                    onvalueschange={(values)=>setRelationValues(rule,values)}
                    onsearchchange={(query)=>void loadOptions(rule.field==='album'?'album':'tag',query)}
                  />
                {:else}
                  <V2Field
                    label="Value"
                    type={inputType(rule.field)}
                    value={rule.value}
                    placeholder={placeholder(rule.field)}
                    step={definition.kind==='number'?'any':undefined}
                    onvalueinput={(value)=>updateRule(rule.id,{value})}
                  />
                {/if}
              {:else}
                <div class="keeper-rule-no-value">No value needed</div>
              {/if}
            </div>
            <V2Button variant="danger" iconOnly ariaLabel="Remove condition" onclick={()=>removeRule(rule.id)}><Trash2 size={15}/> </V2Button>
          </div>
        </V2Card>
      {/each}
    </div>

    {#if preview}
      <V2Card>
        <V2Stack gap="sm">
          <strong>{preview.wouldApplyGroupCount.toLocaleString()} groups can be auto-selected</strong>
          <div class="keeper-preview-grid">
            <span><b>{preview.matchedGroupCount.toLocaleString()}</b> matched</span>
            <span><b>{preview.validGroupCount.toLocaleString()}</b> valid</span>
            <span><b>{preview.ambiguousGroupCount.toLocaleString()}</b> ambiguous</span>
            <span><b>{preview.blockedGroupCount.toLocaleString()}</b> blocked</span>
            <span><b>{preview.preservedManualGroupCount.toLocaleString()}</b> manual choices preserved</span>
            <span><b>{preview.trashCount.toLocaleString()}</b> assets marked Delete</span>
          </div>
          {#if preview.limitExceeded}<p class="keeper-warning">The matching set exceeds the configured action limit. Narrow the current filters before applying.</p>{/if}
        </V2Stack>
      </V2Card>
    {/if}
    {#if error}<p class="keeper-error" role="alert">{error}</p>{/if}
  </V2Stack>

  {#snippet footer()}
    <V2Inline gap="sm">
      <V2Button disabled={!canRun} onclick={()=>void runPreview()}>{busy?'Working…':'Preview'}</V2Button>
      <V2Button variant="primary" disabled={!canRun||Boolean(preview?.limitExceeded)} onclick={()=>void applyRules()}>{busy?'Working…':'Generate drafts'}</V2Button>
      <V2Button onclick={onclose}>Close</V2Button>
    </V2Inline>
  {/snippet}
</V2Modal>

<style>
  .keeper-grid{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr))}
  .keeper-rules-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
  .keeper-rules-heading h3{margin:0 0 4px}
  .keeper-rules-heading p{margin:0;color:var(--v2-text-muted);max-width:760px}
  .keeper-rule-list{display:grid;gap:10px}
  .keeper-rule-row{display:grid;grid-template-columns:auto minmax(120px,.7fr) minmax(180px,1.25fr) minmax(150px,1fr) minmax(180px,1.2fr) auto;gap:10px;align-items:end}
  .keeper-rule-order{display:flex;align-items:center;gap:4px;padding-bottom:2px}
  .keeper-rule-order span{min-width:22px;text-align:center;font-variant-numeric:tabular-nums}
  .keeper-rule-no-value{min-height:40px;display:flex;align-items:center;color:var(--v2-text-muted);font-size:.9rem}
  .keeper-preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 16px}
  .keeper-warning,.keeper-error{margin:0;color:var(--v2-danger)}
  @media (max-width:900px){
    .keeper-grid,.keeper-preview-grid{grid-template-columns:1fr}
    .keeper-rule-row{grid-template-columns:1fr 1fr}
    .keeper-rule-order{grid-column:1/-1}
  }
</style>
