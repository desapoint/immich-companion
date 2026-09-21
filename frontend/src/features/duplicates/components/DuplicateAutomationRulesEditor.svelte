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
  import {
    automationActionOptions, automationConditionFieldOptions, automationConditionNeedsValue, automationConditionScopeOptions,
    automationFlowOptions, automationOperatorOptions, automationTargetOptions,
    type DuplicateAutomationBranchAction, type DuplicateAutomationConditionField, type DuplicateAutomationConditionScope,
    type DuplicateAutomationUiCondition, type DuplicateAutomationUiRule,
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
    addCondition: (ruleId: number, scope?: DuplicateAutomationConditionScope) => void;
    removeCondition: (ruleId: number, conditionId: number) => void;
    updateCondition: (ruleId: number, conditionId: number, patch: Partial<DuplicateAutomationUiCondition>) => void;
    loadOptions: (kind: 'album' | 'tag', query?: string) => void | Promise<void>;
    conditionInputKind: (condition: DuplicateAutomationUiCondition) => string;
    placeholder: (field: DuplicateAutomationConditionField) => string;
    setConditionRelations: (ruleId: number, condition: DuplicateAutomationUiCondition, values: string[]) => void;
  } = $props();

  const rootLogicItems=[{value:'all',label:'All'},{value:'any',label:'Any'}];
  const searchScopeOptions=automationConditionScopeOptions.filter((item)=>item.value!=='member');
  const nonMatchActionOptions=[{value:'none',label:'No action'},...automationActionOptions];

  function relationValues(value: string): string[] { return value.split(',').map((part) => part.trim()).filter(Boolean); }
</script>

<div class="automation-heading">
  <div>
    <h3>Expert automation rules</h3>
    <p>Build each rule like an expert search: qualify duplicate groups, filter members inside those groups, then define what happens to matching and non-matching members.</p>
  </div>
  <V2Button onclick={addRule}><Plus size={15}/> Add rule</V2Button>
</div>

<div class="automation-rule-list">
  {#each rules as rule,index (rule.id)}
    {@const searchConditions=rule.conditions.filter((condition)=>condition.scope!=='member')}
    {@const matchConditions=rule.conditions.filter((condition)=>condition.scope==='member')}
    <V2Card>
      <V2Stack gap="md">
        <div class="automation-rule-header">
          <V2Inline gap="sm" wrap>
            <V2Button iconOnly ariaLabel="Move rule up" disabled={index===0} onclick={()=>moveRule(index,-1)}><ArrowUp size={15}/></V2Button>
            <V2Badge text={'Rule '+(index+1)}/>
            <V2Button iconOnly ariaLabel="Move rule down" disabled={index===rules.length-1} onclick={()=>moveRule(index,1)}><ArrowDown size={15}/></V2Button>
          </V2Inline>
          <V2Inline gap="sm" wrap>
            <span class="v2-small v2-muted">Root matching</span>
            <V2Segmented items={rootLogicItems} active={rule.logic} ariaLabel={'Rule '+(index+1)+' matching'} onselect={(value)=>updateRule(rule.id,{logic:value as DuplicateAutomationUiRule['logic']})}/>
            <V2Button variant="danger" iconOnly ariaLabel="Remove rule" onclick={()=>removeRule(rule.id)}><Trash2 size={15}/></V2Button>
          </V2Inline>
        </div>

        <div class="expert-stage">
          <div class="stage-heading">
            <div>
              <V2Badge text="1 · Search"/>
              <h4>Qualify duplicate groups</h4>
              <p>These conditions decide which groups enter the rule. Group and aggregate-member conditions belong here.</p>
            </div>
            <V2Button onclick={()=>addCondition(rule.id,'group')}><Plus size={15}/> Search condition</V2Button>
          </div>
          {#if searchConditions.length===0}
            <div class="empty-stage">No search conditions. Every duplicate group in the selected automation scope reaches the member filter.</div>
          {:else}
            <div class="condition-list">
              {#each searchConditions as condition (condition.id)}
                {@const conditionKind=conditionInputKind(condition)}
                {@const operators=automationOperatorOptions(condition)}
                <div class="condition-row condition-row--search">
                  <SelectField id={'condition-scope-'+condition.id} label="Scope" value={condition.scope} options={[...searchScopeOptions]} onchange={(value)=>updateCondition(rule.id,condition.id,{scope:value as DuplicateAutomationConditionScope})}/>
                  <SelectField id={'condition-field-'+condition.id} label="Field" value={condition.field} options={automationConditionFieldOptions(condition.scope)} searchable onchange={(value)=>updateCondition(rule.id,condition.id,{field:value as DuplicateAutomationConditionField})}/>
                  <SelectField id={'condition-op-'+condition.id} label="Match" value={condition.operator} options={[...operators]} onchange={(value)=>updateCondition(rule.id,condition.id,{operator:value as DuplicateAutomationUiCondition['operator']})}/>
                  {#if automationConditionNeedsValue(condition)}
                    {#if conditionKind==='media'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='availability'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='date'}<DateTimePickerField id={'condition-value-'+condition.id} label="Value" value={condition.value} showTime onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='relation'}<SelectField id={'condition-value-'+condition.id} label="Value" multiple values={relationValues(condition.value)} options={condition.field==='album'?albumOptions:tagOptions} searchable loading={condition.field==='album'?albumLoading:tagLoading} searchPlaceholder={'Search '+condition.field+'s…'} onvalueschange={(values)=>setConditionRelations(rule.id,condition,values)} onsearchchange={(query)=>void loadOptions(condition.field==='album'?'album':'tag',query)}/>
                    {:else if condition.field==='classification'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} multiple values={relationValues(condition.value)} options={[{value:'exact file',label:'Exact file'},{value:'exact pixels',label:'Exact pixels'},{value:'likely same',label:'Likely same'},{value:'similar',label:'Similar'},{value:'mismatch',label:'Mismatch'},{value:'unverified',label:'Unverified'},{value:'unavailable',label:'Unavailable'},{value:'ineligible',label:'Ineligible'}]} onvalueschange={(values)=>updateCondition(rule.id,condition.id,{value:values.join(',')})}/>
                    {:else if condition.field==='review_state'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={['Actionable','Needs review','Needs decisions','Blocked'].map((value)=>({value,label:value}))} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if condition.field==='discovery_source'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={[{value:'immich_duplicate',label:'Immich'},{value:'companion_similarity',label:'Similarity'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else}<V2Field label="Value" type={conditionKind==='number'?'number':'text'} value={condition.value} placeholder={placeholder(condition.field)} step={conditionKind==='number'?'any':undefined} onvalueinput={(value)=>updateCondition(rule.id,condition.id,{value})}/>{/if}
                  {:else}<div class="no-value">No value needed</div>{/if}
                  {#if condition.scope==='at_least_members'}<V2Field label="N" type="number" value={String(condition.count)} min="1" step="1" onvalueinput={(value)=>updateCondition(rule.id,condition.id,{count:Math.max(1,Number.parseInt(value||'1',10)||1)})}/>{/if}
                  <V2Button variant="danger" iconOnly ariaLabel="Remove search condition" onclick={()=>removeCondition(rule.id,condition.id)}><Trash2 size={15}/></V2Button>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <div class="expert-stage">
          <div class="stage-heading">
            <div>
              <V2Badge text="2 · Match filter"/>
              <h4>Choose members inside matching groups</h4>
              <p>The member filter partitions a qualifying group into Match and Non-match sets before actions are considered.</p>
            </div>
            <V2Button onclick={()=>addCondition(rule.id,'member')}><Plus size={15}/> Match condition</V2Button>
          </div>
          {#if matchConditions.length===0}
            <div class="empty-stage automation-warning">Add at least one member condition to make the Match set explicit.</div>
          {:else}
            <div class="condition-list">
              {#each matchConditions as condition (condition.id)}
                {@const conditionKind=conditionInputKind(condition)}
                {@const operators=automationOperatorOptions(condition)}
                <div class="condition-row condition-row--member">
                  <div class="member-scope"><span class="v2-field-label">Scope</span><V2Badge text="Member"/></div>
                  <SelectField id={'condition-field-'+condition.id} label="Field" value={condition.field} options={automationConditionFieldOptions('member')} searchable onchange={(value)=>updateCondition(rule.id,condition.id,{field:value as DuplicateAutomationConditionField})}/>
                  <SelectField id={'condition-op-'+condition.id} label="Match" value={condition.operator} options={[...operators]} onchange={(value)=>updateCondition(rule.id,condition.id,{operator:value as DuplicateAutomationUiCondition['operator']})}/>
                  {#if automationConditionNeedsValue(condition)}
                    {#if conditionKind==='media'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='availability'}<SelectField id={'condition-value-'+condition.id} label="Value" value={condition.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='date'}<DateTimePickerField id={'condition-value-'+condition.id} label="Value" value={condition.value} showTime onchange={(value: string)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='relation'}<SelectField id={'condition-value-'+condition.id} label="Value" multiple values={relationValues(condition.value)} options={condition.field==='album'?albumOptions:tagOptions} searchable loading={condition.field==='album'?albumLoading:tagLoading} searchPlaceholder={'Search '+condition.field+'s…'} onvalueschange={(values)=>setConditionRelations(rule.id,condition,values)} onsearchchange={(query)=>void loadOptions(condition.field==='album'?'album':'tag',query)}/>
                    {:else}<V2Field label="Value" type={conditionKind==='number'?'number':'text'} value={condition.value} placeholder={placeholder(condition.field)} step={conditionKind==='number'?'any':undefined} onvalueinput={(value)=>updateCondition(rule.id,condition.id,{value})}/>{/if}
                  {:else}<div class="no-value">No value needed</div>{/if}
                  <V2Button variant="danger" iconOnly ariaLabel="Remove match condition" onclick={()=>removeCondition(rule.id,condition.id)}><Trash2 size={15}/></V2Button>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <div class="expert-stage">
          <div class="stage-heading">
            <div>
              <V2Badge text="3 · Actions"/>
              <h4>Act on Match and Non-match sets</h4>
              <p>The Match branch remains wired to the current automation evaluator. The Non-match branch is intentionally UI-only on this branch.</p>
            </div>
            <V2Inline gap="sm" wrap>
              <V2Button disabled title="UI-only branch: search navigation is not wired yet">View search</V2Button>
              <V2Button disabled title="UI-only branch: member highlighting is not wired yet">Show member matches</V2Button>
            </V2Inline>
          </div>
          <div class="branch-grid">
            <div class="action-branch action-branch--match">
              <V2Inline justify="between" wrap><strong>Match</strong><V2Badge text="Current execution"/></V2Inline>
              <SelectField id={'automation-target-'+rule.id} label="Apply Match action to" value={rule.target} options={[...automationTargetOptions]} onchange={(value)=>updateRule(rule.id,{target:value as DuplicateAutomationUiRule['target']})}/>
              <SelectField id={'automation-action-'+rule.id} label="Action" value={rule.action} options={[...automationActionOptions]} onchange={(value)=>updateRule(rule.id,{action:value as DuplicateAutomationUiRule['action']})}/>
              {#if rule.action==='resolve_keeper'}<span class="v2-small v2-muted">Uses the keeper priority rules below to choose the survivor.</span>{/if}
            </div>
            <div class="action-branch action-branch--nonmatch">
              <V2Inline justify="between" wrap><strong>Non-match</strong><V2Badge text="UI only"/></V2Inline>
              <SelectField id={'automation-non-match-action-'+rule.id} label="Action" value={rule.nonMatchAction??'none'} options={nonMatchActionOptions} onchange={(value)=>updateRule(rule.id,{nonMatchAction:value as DuplicateAutomationBranchAction})}/>
              <span class="v2-small v2-muted">This branch will act on selected members that do not satisfy the Match filter. Execution wiring is deliberately deferred.</span>
              {#if rule.nonMatchAction==='resolve_keeper'}<span class="v2-small v2-muted">Keeper resolution will use the keeper priority rules below once this branch is wired.</span>{/if}
            </div>
          </div>
          <SelectField id={'automation-flow-'+rule.id} label="After this rule" value={rule.flow} options={[...automationFlowOptions]} onchange={(value)=>updateRule(rule.id,{flow:value as DuplicateAutomationUiRule['flow']})}/>
          {#if rule.target==='matching_members'&&matchConditions.length===0}<p class="automation-warning">Matching members needs at least one Match filter condition.</p>{/if}
          {#if rule.nonMatchAction&&rule.nonMatchAction!=='none'}<p class="automation-warning">A Non-match action is configured. Preview and Generate decisions are disabled until Non-match execution is implemented.</p>{/if}
        </div>
      </V2Stack>
    </V2Card>
  {/each}
</div>

<style>
  .automation-heading,.automation-rule-header,.stage-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
  .automation-heading h3,.stage-heading h4{margin:0 0 4px}.automation-heading p,.stage-heading p{margin:0;color:var(--v2-text-muted);max-width:820px}
  .automation-rule-list,.condition-list{display:grid;gap:10px}
  .expert-stage{position:relative;padding:.8rem;border:1px solid color-mix(in srgb,var(--v2-accent,#8b5cf6) 34%,var(--v2-border,rgba(127,127,127,.3)));border-inline-start:3px solid var(--v2-accent,#8b5cf6);border-radius:.7rem;background:color-mix(in srgb,var(--v2-accent,#8b5cf6) 4%,var(--v2-surface,Canvas))}
  .stage-heading{margin-bottom:10px}.stage-heading h4{margin-top:6px}.empty-stage{padding:.75rem;border:1px dashed var(--v2-line);border-radius:.55rem;color:var(--v2-text-muted)}
  .condition-row{display:grid;grid-template-columns:minmax(130px,.8fr) minmax(170px,1.2fr) minmax(140px,.9fr) minmax(170px,1fr) minmax(80px,.4fr) auto;gap:10px;align-items:end}
  .condition-row--member{grid-template-columns:minmax(100px,.55fr) minmax(180px,1.25fr) minmax(150px,1fr) minmax(180px,1.2fr) auto}.member-scope{display:grid;gap:6px;align-self:stretch;align-content:end;padding-bottom:7px}
  .branch-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px}.action-branch{display:grid;gap:10px;padding:.75rem;border:1px solid var(--v2-line);border-radius:.6rem;background:var(--v2-surface)}.action-branch--nonmatch{border-style:dashed}
  .no-value{min-height:40px;display:flex;align-items:center;color:var(--v2-text-muted);font-size:.9rem}.automation-warning{margin:0;color:var(--v2-danger)}
  @media(max-width:1050px){.condition-row,.condition-row--member{grid-template-columns:1fr 1fr 1fr}.branch-grid{grid-template-columns:1fr}}
  @media(max-width:760px){.condition-row,.condition-row--member{grid-template-columns:1fr}.automation-heading,.automation-rule-header,.stage-heading{align-items:stretch;flex-direction:column}}
</style>
