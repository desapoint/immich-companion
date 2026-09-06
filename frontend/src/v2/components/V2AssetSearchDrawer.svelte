<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2Stack from './V2Stack.svelte';
  import { assetExpressionText,assetFieldSelectOptions,assetOperatorSelectOptions,type AssetGroup,type AssetRule } from '../state/assetSearch';

  let { rules=$bindable<AssetRule[]>([]),groups=$bindable<AssetGroup[]>([]),logic=$bindable<'AND'|'OR'>('AND'),negated=$bindable(false),onclose,onapply }:{rules?:AssetRule[];groups?:AssetGroup[];logic?:'AND'|'OR';negated?:boolean;onclose:()=>void;onapply:()=>void}=$props();
  let seq=$state(Math.max(0,...rules.flatMap((rule)=>[rule.id]),...groups.flatMap((group)=>[group.id,...group.rules.map((rule)=>rule.id)])));
  const expression=$derived(assetExpressionText(rules,groups,logic,negated));
  function addRule(group?:AssetGroup){const rule={id:++seq,field:'filename',op:'contains',value:''};if(group)group.rules=[...group.rules,rule];else rules=[...rules,rule]}
  function removeRule(id:number,group?:AssetGroup){if(group)group.rules=group.rules.filter((rule)=>rule.id!==id);else rules=rules.filter((rule)=>rule.id!==id)}
  function addGroup(){groups=[...groups,{id:++seq,logic:'AND',negated:false,rules:[{id:++seq,field:'tag',op:'is',value:''}]}]}
  function reset(){rules=[];groups=[];logic='AND';negated=false}
</script>

<button type="button" class="v2-drawer-backdrop" aria-label="Close expert search editor" onclick={onclose}></button>
<aside class="v2-drawer">
  <div class="v2-drawer-head"><div><h2>Build asset search expression</h2><p class="v2-muted">Edit the draft here. Results change only when you apply/search.</p></div><V2Button onclick={onclose}>✕</V2Button></div>
  <div class="v2-drawer-body">
    <V2Section title="Expression structure"><V2Stack gap="md">
      <V2Card><V2Stack gap="sm"><V2Inline justify="between" wrap><V2Inline gap="sm"><V2Badge text="Root group"/><V2Segmented items={['AND','OR']} active={logic} onselect={(value)=>logic=value as 'AND'|'OR'} ariaLabel="Root group logic"/><V2Checkbox label="NOT group" checked={negated} onchange={(checked)=>negated=checked}/></V2Inline></V2Inline>
        {#each rules as rule}<div class="v2-expert-rule"><SelectField id={`expert-root-field-${rule.id}`} value={rule.field} options={assetFieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-root-op-${rule.id}`} value={rule.op} options={assetOperatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value} placeholder="Value…"><V2Button onclick={()=>removeRule(rule.id)}>✕</V2Button></div>{/each}
        <V2Inline gap="sm"><V2Button onclick={()=>addRule()}>+ Rule</V2Button><V2Button onclick={addGroup}>+ Nested group</V2Button></V2Inline>
      </V2Stack></V2Card>
      {#each groups as group}<V2Card><V2Stack gap="sm"><V2Inline justify="between"><V2Inline gap="sm"><V2Badge text="Nested group"/><V2Segmented items={['AND','OR']} active={group.logic} onselect={(value)=>group.logic=value as 'AND'|'OR'} ariaLabel="Nested group logic"/><V2Checkbox label="NOT group" checked={group.negated} onchange={(checked)=>group.negated=checked}/></V2Inline><V2Button onclick={()=>groups=groups.filter((item)=>item.id!==group.id)}>Remove group</V2Button></V2Inline>
        {#each group.rules as rule}<div class="v2-expert-rule"><SelectField id={`expert-group-${group.id}-field-${rule.id}`} value={rule.field} options={assetFieldSelectOptions} onchange={(value)=>rule.field=value}/><SelectField id={`expert-group-${group.id}-op-${rule.id}`} value={rule.op} options={assetOperatorSelectOptions} onchange={(value)=>rule.op=value}/><input bind:value={rule.value}><V2Button onclick={()=>removeRule(rule.id,group)}>✕</V2Button></div>{/each}<V2Button onclick={()=>addRule(group)}>+ Rule</V2Button>
      </V2Stack></V2Card>{/each}
    </V2Stack></V2Section>
    <V2Section title="Expression preview"><div class="v2-expression">{expression}</div></V2Section>
  </div>
  <div class="v2-drawer-foot"><V2Badge text={`${rules.length+groups.reduce((count,group)=>count+group.rules.length,0)} rules · ${groups.length} groups`}/><V2Inline gap="sm"><V2Button onclick={reset}>Reset</V2Button><V2Button onclick={onclose}>Cancel</V2Button><V2Button variant="primary" onclick={onapply}>Apply & Search</V2Button></V2Inline></div>
</aside>
