<script lang="ts">
  import { ArrowDown, ArrowUp, Plus, Trash2 } from '@lucide/svelte';
  import DateTimePickerField from '../../../v2/components/DateTimePickerField.svelte';
  import SelectField, { type SelectOption } from '../../../v2/components/SelectField.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Card from '../../../v2/components/V2Card.svelte';
  import V2Field from '../../../v2/components/V2Field.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';
  import { keeperEffectOptions, keeperFieldDefinition, keeperOperatorOptions, keeperPresetNames, keeperRuleFieldOptions, keeperRuleNeedsValue, type DuplicateKeeperUiRule } from '../../../v2/state/duplicateKeeperRules';
  import type { DuplicateKeeperRuleField } from '../../../v2/data/contracts';

  let {
    rules, presetName, albumOptions, tagOptions, albumLoading, tagLoading, setPreset, updateRule, addRule, removeRule, moveRule, loadOptions,
  }: {
    rules: DuplicateKeeperUiRule[];
    presetName: string;
    albumOptions: SelectOption[];
    tagOptions: SelectOption[];
    albumLoading: boolean;
    tagLoading: boolean;
    setPreset: (value: string) => void;
    updateRule: (id: number, patch: Partial<DuplicateKeeperUiRule>) => void;
    addRule: () => void;
    removeRule: (id: number) => void;
    moveRule: (index: number, direction: -1 | 1) => void;
    loadOptions: (kind: 'album' | 'tag', query?: string) => void | Promise<void>;
  } = $props();

  function relationValues(value: string): string[] { return value.split(',').map((part) => part.trim()).filter(Boolean); }
  function setRelations(rule: DuplicateKeeperUiRule, values: string[]): void { updateRule(rule.id, { value: values.join(',') }); }
</script>

<div class="automation-heading"><div><h3>Keeper priority</h3><p>Used only when a rule chooses “Resolve using keeper priority”. Require filters candidates first; Prefer and Avoid then narrow them in order. A remaining tie uses the current reference, otherwise the group stays for manual review.</p></div><V2Button onclick={addRule}><Plus size={15}/> Add keeper condition</V2Button></div>
<V2Card><SelectField id="keeper-preset" label="Keeper preset" value={presetName} options={keeperPresetNames.map((value)=>({value,label:value}))} onchange={setPreset}/></V2Card>
<div class="keeper-rule-list">
  {#each rules as rule,index (rule.id)}
    {@const definition=keeperFieldDefinition(rule.field)}{@const operators=keeperOperatorOptions(rule.field,rule.effect)}
    <V2Card>
      <div class="keeper-rule-row">
        <div class="rule-order"><V2Button iconOnly ariaLabel="Move keeper condition up" disabled={index===0} onclick={()=>moveRule(index,-1)}><ArrowUp size={15}/></V2Button><span>{index+1}</span><V2Button iconOnly ariaLabel="Move keeper condition down" disabled={index===rules.length-1} onclick={()=>moveRule(index,1)}><ArrowDown size={15}/></V2Button></div>
        <SelectField id={`keeper-effect-${rule.id}`} label="Behavior" value={rule.effect} options={keeperEffectOptions} onchange={(value)=>updateRule(rule.id,{effect:value as DuplicateKeeperUiRule['effect']})}/>
        <SelectField id={`keeper-field-${rule.id}`} label="Condition" value={rule.field} options={keeperRuleFieldOptions} searchable onchange={(value)=>updateRule(rule.id,{field:value as DuplicateKeeperRuleField})}/>
        <SelectField id={`keeper-operator-${rule.id}`} label="Match" value={rule.operator} options={[...operators]} onchange={(value)=>updateRule(rule.id,{operator:value as DuplicateKeeperUiRule['operator']})}/>
        <div>{#if keeperRuleNeedsValue(rule)}
          {#if definition.kind==='media'}<SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateRule(rule.id,{value})}/>
          {:else if definition.kind==='availability'}<SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value: string)=>updateRule(rule.id,{value})}/>
          {:else if definition.kind==='date'}<DateTimePickerField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} showTime onchange={(value: string)=>updateRule(rule.id,{value})}/>
          {:else if definition.kind==='relation'}<SelectField id={`keeper-value-${rule.id}`} label="Value" multiple values={relationValues(rule.value)} options={rule.field==='album'?albumOptions:tagOptions} searchable loading={rule.field==='album'?albumLoading:tagLoading} onvalueschange={(values)=>setRelations(rule,values)} onsearchchange={(query)=>void loadOptions(rule.field==='album'?'album':'tag',query)}/>
          {:else}<V2Field label="Value" type={definition.kind==='number'?'number':'text'} value={rule.value} step={definition.kind==='number'?'any':undefined} onvalueinput={(value)=>updateRule(rule.id,{value})}/>{/if}
        {:else}<div class="no-value">No value needed</div>{/if}</div>
        <V2Button variant="danger" iconOnly ariaLabel="Remove keeper condition" onclick={()=>removeRule(rule.id)}><Trash2 size={15}/></V2Button>
      </div>
    </V2Card>
  {/each}
</div>

<style>
  .automation-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}.automation-heading h3{margin:0 0 4px}.automation-heading p{margin:0;color:var(--v2-text-muted);max-width:820px}.keeper-rule-list{display:grid;gap:10px}.keeper-rule-row{display:grid;grid-template-columns:auto minmax(120px,.7fr) minmax(180px,1.25fr) minmax(150px,1fr) minmax(180px,1.2fr) auto;gap:10px;align-items:end}.rule-order{display:flex;align-items:center;gap:6px}.rule-order span{min-width:22px;text-align:center;font-variant-numeric:tabular-nums}.no-value{min-height:40px;display:flex;align-items:center;color:var(--v2-text-muted);font-size:.9rem}
  @media(max-width:1050px){.keeper-rule-row{grid-template-columns:1fr 1fr}.rule-order{grid-column:1/-1}}@media(max-width:760px){.automation-heading{align-items:stretch;flex-direction:column}}
</style>
