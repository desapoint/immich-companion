<script lang="ts">
  import { ArrowDown, ArrowUp, Plus, Trash2 } from '@lucide/svelte';
  import DateTimePickerField from '../../../lib/components/ui/DateTimePickerField.svelte';
  import SelectField, { type SelectOption } from '../../../lib/components/ui/SelectField.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2Segmented from '../../../lib/components/ui/Segmented.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import { keeperEffectOptions, keeperFieldDefinition, keeperOperatorOptions, keeperPresetNames, keeperRuleFieldOptions, keeperRuleNeedsValue, type DuplicateKeeperUiRule } from '../state/duplicateKeeperRules';
  import type { DuplicateKeeperRuleField } from '../types/contracts';

  let {
    rules, presetName, mode='preset', usageCount=0, albumOptions, tagOptions, albumLoading, tagLoading, setMode, setPreset, updateRule, addRule, removeRule, moveRule, loadOptions,
  }: {
    rules: DuplicateKeeperUiRule[];
    presetName: string;
    mode?: 'preset'|'expert';
    usageCount?: number;
    albumOptions: SelectOption[];
    tagOptions: SelectOption[];
    albumLoading: boolean;
    tagLoading: boolean;
    setMode: (value: 'preset'|'expert') => void;
    setPreset: (value: string) => void;
    updateRule: (id: number, patch: Partial<DuplicateKeeperUiRule>) => void;
    addRule: () => void;
    removeRule: (id: number) => void;
    moveRule: (index: number, direction: -1 | 1) => void;
    loadOptions: (kind: 'album' | 'tag', query?: string) => void | Promise<void>;
  } = $props();

  const keeperModeItems=[{value:'preset',label:'Preset'},{value:'expert',label:'Expert'}];

  function relationValues(value: string): string[] { return value.split(',').map((part) => part.trim()).filter(Boolean); }
  function setRelations(rule: DuplicateKeeperUiRule, values: string[]): void { updateRule(rule.id, { value: values.join(',') }); }
  function effectLabel(rule: DuplicateKeeperUiRule): string { return keeperEffectOptions.find((item)=>item.value===rule.effect)?.label??rule.effect; }
  function fieldLabel(rule: DuplicateKeeperUiRule): string { return keeperFieldDefinition(rule.field).label; }
  function operatorLabel(rule: DuplicateKeeperUiRule): string { return keeperOperatorOptions(rule.field,rule.effect).find((item)=>item.value===rule.operator)?.label??rule.operator; }
  function ruleSummary(rule: DuplicateKeeperUiRule): string {
    const value=keeperRuleNeedsValue(rule)&&rule.value.trim()?' · '+rule.value.trim():'';
    return effectLabel(rule)+' · '+fieldLabel(rule)+' · '+operatorLabel(rule)+value;
  }
</script>

<div id="automation-keeper-priority" class="keeper-shell">
  <div class="automation-heading">
    <div>
      <h3>Keeper strategy</h3>
      <p>Used only by actions that resolve a candidate set to one keeper. Required conditions filter candidates first; Prefer and Avoid are ordered tiebreakers. A remaining tie uses the current reference when possible.</p>
    </div>
    <V2Inline gap="sm" wrap>
      <V2Badge text={usageCount===1?'Used by 1 action':'Used by '+usageCount+' actions'}/>
      <V2Button disabled={mode!=='expert'} onclick={addRule}><Plus size={15}/> Add keeper condition</V2Button>
    </V2Inline>
  </div>

  <V2Card>
    <V2Stack gap="md">
      <div class="keeper-mode-row">
        <div>
          <span class="v2-field-label">Keeper mode</span>
          <p class="v2-small v2-muted">Preset keeps a named strategy intact. Expert exposes the ordered keeper conditions directly.</p>
        </div>
        <V2Segmented items={keeperModeItems} active={mode} ariaLabel="Keeper strategy mode" onselect={(value)=>setMode(value as 'preset'|'expert')}/>
      </div>

      {#if mode==='preset'}
        <div class="preset-grid">
          <SelectField id="keeper-preset" label="Keeper preset" value={presetName} options={keeperPresetNames.map((value)=>({value,label:value}))} onchange={setPreset}/>
          <div class="mode-note">
            <strong>Preset strategy</strong>
            <span class="v2-small v2-muted">The preset expands to the ordered rules below. Switch to Expert to customize them without changing how keeper resolution works.</span>
          </div>
        </div>
        <div class="keeper-summary">
          {#each rules as rule,index (rule.id)}
            <div class="summary-row"><V2Badge text={String(index+1)}/><span>{ruleSummary(rule)}</span></div>
          {/each}
        </div>
      {:else}
        <div class="mode-note mode-note--expert">
          <strong>Expert keeper priority</strong>
          <span class="v2-small v2-muted">Conditions run from top to bottom. Require removes candidates that do not match. Prefer narrows to matching candidates when possible. Avoid removes matching candidates when another candidate remains.</span>
        </div>
      {/if}
    </V2Stack>
  </V2Card>

  {#if mode==='expert'}
    <div class="keeper-rule-list">
      {#each rules as rule,index (rule.id)}
        {@const definition=keeperFieldDefinition(rule.field)}
        {@const operators=keeperOperatorOptions(rule.field,rule.effect)}
        <div class="keeper-expert-rule">
          <V2Stack gap="sm">
            <div class="keeper-rule-heading">
              <V2Inline gap="sm" wrap>
                <V2Button iconOnly ariaLabel="Move keeper condition up" disabled={index===0} onclick={()=>moveRule(index,-1)}><ArrowUp size={15}/></V2Button>
                <V2Badge text={'Priority '+(index+1)}/>
                <V2Button iconOnly ariaLabel="Move keeper condition down" disabled={index===rules.length-1} onclick={()=>moveRule(index,1)}><ArrowDown size={15}/></V2Button>
              </V2Inline>
              <V2Button variant="danger" iconOnly ariaLabel="Remove keeper condition" onclick={()=>removeRule(rule.id)}><Trash2 size={15}/></V2Button>
            </div>

            <div class="keeper-rule-row">
              <SelectField id={'keeper-effect-'+rule.id} label="Behavior" value={rule.effect} options={keeperEffectOptions} onchange={(value)=>updateRule(rule.id,{effect:value as DuplicateKeeperUiRule['effect']})}/>
              <SelectField id={'keeper-field-'+rule.id} label="Field" value={rule.field} options={keeperRuleFieldOptions} searchable searchPlaceholder="Find a keeper field…" onchange={(value)=>updateRule(rule.id,{field:value as DuplicateKeeperRuleField})}/>
              <SelectField id={'keeper-operator-'+rule.id} label="Match / rank" value={rule.operator} options={[...operators]} onchange={(value)=>updateRule(rule.id,{operator:value as DuplicateKeeperUiRule['operator']})}/>
              <div>
                {#if keeperRuleNeedsValue(rule)}
                  {#if definition.kind==='media'}<SelectField id={'keeper-value-'+rule.id} label="Value" value={rule.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateRule(rule.id,{value})}/>
                  {:else if definition.kind==='availability'}<SelectField id={'keeper-value-'+rule.id} label="Value" value={rule.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value: string)=>updateRule(rule.id,{value})}/>
                  {:else if definition.kind==='date'}<DateTimePickerField id={'keeper-value-'+rule.id} label="Value" value={rule.value} showTime onchange={(value: string)=>updateRule(rule.id,{value})}/>
                  {:else if definition.kind==='relation'}<SelectField id={'keeper-value-'+rule.id} label="Value" multiple values={relationValues(rule.value)} options={rule.field==='album'?albumOptions:tagOptions} searchable loading={rule.field==='album'?albumLoading:tagLoading} searchPlaceholder={'Search '+rule.field+'s…'} onvalueschange={(values)=>setRelations(rule,values)} onsearchchange={(query)=>void loadOptions(rule.field==='album'?'album':'tag',query)}/>
                  {:else}<V2Field label="Value" type={definition.kind==='number'?'number':'text'} value={rule.value} step={definition.kind==='number'?'any':undefined} onvalueinput={(value)=>updateRule(rule.id,{value})}/>{/if}
                {:else}
                  <div class="no-value"><span class="v2-field-label">Value</span><span>Determined by ranking operator</span></div>
                {/if}
              </div>
            </div>
            <span class="v2-small v2-muted">{keeperEffectOptions.find((item)=>item.value===rule.effect)?.subtitle}</span>
          </V2Stack>
        </div>
      {/each}
      {#if rules.length===0}<div class="empty-keeper">No keeper conditions. Add one before using keeper resolution.</div>{/if}
    </div>
  {/if}

  <V2Card>
    <V2Stack gap="sm">
      <V2Inline gap="sm" wrap><V2Badge text="Resolution order"/><strong>Require → Prefer / Avoid → current reference fallback</strong></V2Inline>
      <span class="v2-small v2-muted">This branch changes presentation only. Keeper selection still uses the existing ordered evaluator and the same safety behavior when no unique keeper can be selected.</span>
    </V2Stack>
  </V2Card>
</div>

<style>
  .keeper-shell,.keeper-rule-list{display:grid;gap:10px}
  .automation-heading,.keeper-mode-row,.keeper-rule-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
  .automation-heading h3{margin:0 0 4px}.automation-heading p{margin:0;color:var(--v2-text-muted);max-width:820px}.keeper-mode-row p{margin:4px 0 0}
  .preset-grid{display:grid;grid-template-columns:minmax(220px,.7fr) minmax(0,1.3fr);gap:12px;align-items:end}
  .mode-note{display:grid;gap:4px;padding:.75rem;border:1px dashed var(--v2-line);border-radius:.55rem}.mode-note--expert{border-style:solid}
  .keeper-summary{display:grid;gap:6px}.summary-row{display:flex;align-items:center;gap:8px;min-height:34px;padding:.35rem .5rem;border:1px solid var(--v2-line);border-radius:.45rem}
  .keeper-expert-rule{position:relative;padding:.8rem;border:1px solid color-mix(in srgb,var(--v2-accent,#8b5cf6) 34%,var(--v2-border,rgba(127,127,127,.3)));border-inline-start:3px solid var(--v2-accent,#8b5cf6);border-radius:.7rem;background:color-mix(in srgb,var(--v2-accent,#8b5cf6) 4%,var(--v2-surface,Canvas))}
  .keeper-rule-row{display:grid;grid-template-columns:minmax(125px,.7fr) minmax(190px,1.25fr) minmax(160px,1fr) minmax(190px,1.15fr);gap:10px;align-items:end}
  .no-value{min-height:40px;display:grid;align-content:end;gap:6px;color:var(--v2-text-muted);font-size:.9rem}.empty-keeper{padding:.75rem;border:1px dashed var(--v2-line);border-radius:.55rem;color:var(--v2-danger)}
  @media(max-width:1050px){.keeper-rule-row,.preset-grid{grid-template-columns:1fr 1fr}}
  @media(max-width:760px){.automation-heading,.keeper-mode-row,.keeper-rule-heading{align-items:stretch;flex-direction:column}.keeper-rule-row,.preset-grid{grid-template-columns:1fr}}
</style>
