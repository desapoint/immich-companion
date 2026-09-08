<script lang="ts">
  import { tick } from 'svelte';
  import V2AssetSearchGroup from './V2AssetSearchGroup.svelte';
  import V2AssetSearchRule from './V2AssetSearchRule.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2Stack from './V2Stack.svelte';
  import type { AssetGroup,AssetRule } from '../state/assetSearch';
  import type { RelationOption } from '../data/contracts';

  let { group,depth=1,albumOptions=[],tagOptions=[],albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,nextId,onchange,onremove,onapply }:{group:AssetGroup;depth?:number;albumOptions?:RelationOption[];tagOptions?:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;onalbumsearch?:(value:string)=>void;ontagsearch?:(value:string)=>void;onalbumloadmore?:()=>void;ontagloadmore?:()=>void;nextId:()=>number;onchange:(group:AssetGroup)=>void;onremove:()=>void;onapply:()=>void}=$props();

  function update(patch:Partial<AssetGroup>){onchange({...group,...patch})}
  function focusRuleField(groupId:number,ruleId:number){void tick().then(()=>requestAnimationFrame(()=>document.getElementById(`expert-group-${groupId}-field-${ruleId}`)?.focus()))}
  function addRule(){const id=nextId();update({rules:[...group.rules,{id,field:'filename',op:'contains',value:''}]});focusRuleField(group.id,id)}
  function changeRule(next:AssetRule){update({rules:group.rules.map((rule)=>rule.id===next.id?next:rule)})}
  function removeRule(id:number){update({rules:group.rules.filter((rule)=>rule.id!==id)})}
  function addGroup(){const groupId=nextId(),ruleId=nextId();update({groups:[...(group.groups??[]),{id:groupId,logic:'AND',negated:false,rules:[{id:ruleId,field:'tag',op:'is',value:''}],groups:[]}]});focusRuleField(groupId,ruleId)}
  function changeChild(next:AssetGroup){update({groups:(group.groups??[]).map((child)=>child.id===next.id?next:child)})}
  function removeChild(id:number){update({groups:(group.groups??[]).filter((child)=>child.id!==id)})}
</script>

<div class="v2-expert-group" data-depth={depth} style={`--v2-search-depth:${depth}`}>
  <V2Stack gap="sm">
    <V2Inline justify="between" wrap>
      <V2Inline gap="sm" wrap>
        <V2Badge text={`Nested group · level ${depth}`}/>
        <V2Segmented items={['AND','OR']} active={group.logic} onselect={(value)=>update({logic:value as 'AND'|'OR'})} ariaLabel={`Nested group level ${depth} logic`}/>
        <V2Checkbox label="NOT group" checked={group.negated} onchange={(checked)=>update({negated:checked})}/>
      </V2Inline>
      <V2Button onclick={onremove}>Remove group</V2Button>
    </V2Inline>

    {#each group.rules as rule (rule.id)}
      <V2AssetSearchRule idPrefix={`expert-group-${group.id}`} {rule} {albumOptions} {tagOptions} {albumLoading} {tagLoading} {albumHasMore} {tagHasMore} {onalbumsearch} {ontagsearch} {onalbumloadmore} {ontagloadmore} onchange={changeRule} onremove={()=>removeRule(rule.id)} {onapply}/>
    {/each}

    {#each group.groups??[] as child (child.id)}
      <V2AssetSearchGroup group={child} depth={depth+1} {albumOptions} {tagOptions} {albumLoading} {tagLoading} {albumHasMore} {tagHasMore} {onalbumsearch} {ontagsearch} {onalbumloadmore} {ontagloadmore} {nextId} onchange={changeChild} onremove={()=>removeChild(child.id)} {onapply}/>
    {/each}

    <V2Inline gap="sm" wrap><V2Button onclick={addRule}>+ Rule</V2Button><V2Button onclick={addGroup}>+ Nested group</V2Button></V2Inline>
  </V2Stack>
</div>

<style>
  .v2-expert-group{position:relative;margin-inline-start:min(calc(var(--v2-search-depth) * .45rem),1.35rem);padding:.8rem;border:1px solid color-mix(in srgb,var(--v2-accent,#8b5cf6) 34%,var(--v2-border,rgba(127,127,127,.3)));border-inline-start:3px solid var(--v2-accent,#8b5cf6);border-radius:.7rem;background:color-mix(in srgb,var(--v2-accent,#8b5cf6) 4%,var(--v2-surface,Canvas))}
</style>
