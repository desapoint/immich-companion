<script lang="ts">
  import { ArrowDown, ArrowUp, Plus, Trash2 } from '@lucide/svelte';
  import DateTimePickerField from '../../../v2/components/DateTimePickerField.svelte';
  import SelectField, { type SelectOption } from '../../../v2/components/SelectField.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Card from '../../../v2/components/V2Card.svelte';
  import V2Field from '../../../v2/components/V2Field.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';
  import {
    automationActionOptions, automationConditionFieldOptions, automationConditionNeedsValue, automationConditionScopeOptions,
    automationFlowOptions, automationOperatorOptions, automationTargetOptions,
    type DuplicateAutomationConditionField, type DuplicateAutomationConditionScope, type DuplicateAutomationUiCondition, type DuplicateAutomationUiRule,
  } from '../state/duplicateAutomationRules';

  let {
    rules, albumOptions, tagOptions, albumLoading, tagLoading, updateRule, addRule, removeRule, moveRule, addCondition, removeCondition,
    updateCondition, loadOptions, conditionInputKind, placeholder, setConditionRelations,
  }: {
    rules: DuplicateAutomationUiRule[];
    albumOptions: SelectOption[];
    tagOptions: SelectOption[];
    albumLoading: boolean;
    tagLoading: boolean;
    updateRule: (id: number, patch: Partial<DuplicateAutomationUiRule>) => void;
    addRule: () => void;
    removeRule: (id: number) => void;
    moveRule: (index: number, direction: -1 | 1) => void;
    addCondition: (ruleId: number) => void;
    removeCondition: (ruleId: number, conditionId: number) => void;
    updateCondition: (ruleId: number, conditionId: number, patch: Partial<DuplicateAutomationUiCondition>) => void;
    loadOptions: (kind: 'album' | 'tag', query?: string) => void | Promise<void>;
    conditionInputKind: (condition: DuplicateAutomationUiCondition) => string;
    placeholder: (field: DuplicateAutomationConditionField) => string;
    setConditionRelations: (ruleId: number, condition: DuplicateAutomationUiCondition, values: string[]) => void;
  } = $props();

  function relationValues(value: string): string[] { return value.split(',').map((part) => part.trim()).filter(Boolean); }
</script>

<div class="automation-heading"><div><h3>Decision rules</h3><p>Each rule has conditions, a target, an action, and flow control. Earlier decisions are protected from later rules. Manual choices are protected unless replacement is explicitly enabled.</p></div><V2Button onclick={addRule}><Plus size={15}/> Add rule</V2Button></div>
<div class="automation-rule-list">
  {#each rules as rule,index (rule.id)}
    <V2Card>
      <V2Stack gap="sm">
        <div class="automation-rule-header">
          <div class="rule-order"><V2Button iconOnly ariaLabel="Move rule up" disabled={index===0} onclick={()=>moveRule(index,-1)}><ArrowUp size={15}/></V2Button><strong>Rule {index+1}</strong><V2Button iconOnly ariaLabel="Move rule down" disabled={index===rules.length-1} onclick={()=>moveRule(index,1)}><ArrowDown size={15}/></V2Button></div>
          <div class="logic-actions"><SelectField id={`automation-logic-${rule.id}`} label="Conditions" value={rule.logic} options={[{value:'all',label:'All must match'},{value:'any',label:'Any may match'}]} onchange={(value)=>updateRule(rule.id,{logic:value as DuplicateAutomationUiRule['logic']})}/><V2Button variant="danger" iconOnly ariaLabel="Remove rule" onclick={()=>removeRule(rule.id)}><Trash2 size={15}/></V2Button></div>
        </div>
        <div class="condition-list">
          {#each rule.conditions as condition (condition.id)}
            {@const conditionKind=conditionInputKind(condition)}
            {@const operators=automationOperatorOptions(condition)}
            <div class="condition-row">
              <SelectField id={`condition-scope-${condition.id}`} label="When" value={condition.scope} options={[...automationConditionScopeOptions]} onchange={(value)=>updateCondition(rule.id,condition.id,{scope:value as DuplicateAutomationConditionScope})}/>
              <SelectField id={`condition-field-${condition.id}`} label="Field" value={condition.field} options={automationConditionFieldOptions(condition.scope)} searchable onchange={(value)=>updateCondition(rule.id,condition.id,{field:value as DuplicateAutomationConditionField})}/>
              <SelectField id={`condition-op-${condition.id}`} label="Match" value={condition.operator} options={[...operators]} onchange={(value)=>updateCondition(rule.id,condition.id,{operator:value as DuplicateAutomationUiCondition['operator']})}/>
              {#if automationConditionNeedsValue(condition)}
                {#if conditionKind==='media'}<SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                {:else if conditionKind==='availability'}<SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                {:else if conditionKind==='date'}<DateTimePickerField id={`condition-value-${condition.id}`} label="Value" value={condition.value} showTime onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                {:else if conditionKind==='relation'}<SelectField id={`condition-value-${condition.id}`} label="Value" multiple values={relationValues(condition.value)} options={condition.field==='album'?albumOptions:tagOptions} searchable loading={condition.field==='album'?albumLoading:tagLoading} searchPlaceholder={`Search ${condition.field}s…`} onvalueschange={(values)=>setConditionRelations(rule.id,condition,values)} onsearchchange={(query)=>void loadOptions(condition.field==='album'?'album':'tag',query)}/>
                {:else if condition.field==='classification'}<SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} multiple values={relationValues(condition.value)} options={[{value:'exact file',label:'Exact file'},{value:'exact pixels',label:'Exact pixels'},{value:'likely same',label:'Likely same'},{value:'similar',label:'Similar'},{value:'mismatch',label:'Mismatch'},{value:'unverified',label:'Unverified'},{value:'unavailable',label:'Unavailable'},{value:'ineligible',label:'Ineligible'}]} onvalueschange={(values)=>updateCondition(rule.id,condition.id,{value:values.join(',')})}/>
                {:else if condition.field==='review_state'}<SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={['Actionable','Needs review','Needs decisions','Blocked'].map((value)=>({value,label:value}))} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                {:else if condition.field==='discovery_source'}<SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'immich_duplicate',label:'Immich'},{value:'companion_similarity',label:'Similarity'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                {:else}<V2Field label="Value" type={conditionKind==='number'?'number':'text'} value={condition.value} placeholder={placeholder(condition.field)} step={conditionKind==='number'?'any':undefined} onvalueinput={(value)=>updateCondition(rule.id,condition.id,{value})}/>{/if}
              {:else}<div class="no-value">No value needed</div>{/if}
              {#if condition.scope==='at_least_members'}<V2Field label="N" type="number" value={String(condition.count)} min="1" step="1" onvalueinput={(value)=>updateCondition(rule.id,condition.id,{count:Math.max(1,Number.parseInt(value||'1',10)||1)})}/>{/if}
              <V2Button variant="danger" iconOnly ariaLabel="Remove condition" disabled={rule.conditions.length===1} onclick={()=>removeCondition(rule.id,condition.id)}><Trash2 size={15}/></V2Button>
            </div>
          {/each}
        </div>
        <V2Button onclick={()=>addCondition(rule.id)}><Plus size={15}/> Add condition</V2Button>
        <div class="rule-actions">
          <SelectField id={`automation-target-${rule.id}`} label="Target" value={rule.target} options={[...automationTargetOptions]} onchange={(value)=>updateRule(rule.id,{target:value as DuplicateAutomationUiRule['target']})}/>
          <SelectField id={`automation-action-${rule.id}`} label="Action" value={rule.action} options={[...automationActionOptions]} onchange={(value)=>updateRule(rule.id,{action:value as DuplicateAutomationUiRule['action']})}/>
          <SelectField id={`automation-flow-${rule.id}`} label="After" value={rule.flow} options={[...automationFlowOptions]} onchange={(value)=>updateRule(rule.id,{flow:value as DuplicateAutomationUiRule['flow']})}/>
        </div>
        {#if rule.target==='matching_members'&&!rule.conditions.some((condition)=>condition.scope==='member')}<p class="automation-warning">Matching members needs at least one condition whose scope is Member.</p>{/if}
      </V2Stack>
    </V2Card>
  {/each}
</div>

<style>
  .automation-heading,.automation-rule-header{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}.automation-heading h3{margin:0 0 4px}.automation-heading p{margin:0;color:var(--v2-text-muted);max-width:820px}.automation-rule-list,.condition-list{display:grid;gap:10px}.rule-order{display:flex;align-items:center;gap:6px}.condition-row{display:grid;grid-template-columns:minmax(130px,.8fr) minmax(170px,1.2fr) minmax(140px,.9fr) minmax(170px,1fr) minmax(80px,.4fr) auto;gap:10px;align-items:end}.rule-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.logic-actions{display:flex;align-items:end;gap:8px}.no-value{min-height:40px;display:flex;align-items:center;color:var(--v2-text-muted);font-size:.9rem}.automation-warning{margin:0;color:var(--v2-danger)}
  @media(max-width:1050px){.condition-row{grid-template-columns:1fr 1fr 1fr}.rule-order{grid-column:1/-1}}@media(max-width:760px){.rule-actions,.condition-row{grid-template-columns:1fr}.automation-heading,.automation-rule-header{align-items:stretch;flex-direction:column}}
</style>
