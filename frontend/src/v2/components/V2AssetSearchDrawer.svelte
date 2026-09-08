<script lang="ts">
  import V2AssetSearchGroup from './V2AssetSearchGroup.svelte';
  import V2AssetSearchRule from './V2AssetSearchRule.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2Stack from './V2Stack.svelte';
  import { assetExpressionText,assetGroupCount,assetRuleCount,maxAssetSearchId,type AssetGroup,type AssetRule } from '../state/assetSearch';
  import type { RelationOption } from '../data/contracts';

  let { rules=$bindable<AssetRule[]>([]),groups=$bindable<AssetGroup[]>([]),logic=$bindable<'AND'|'OR'>('AND'),negated=$bindable(false),albumOptions=[],tagOptions=[],albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,onclose,onapply }:{rules?:AssetRule[];groups?:AssetGroup[];logic?:'AND'|'OR';negated?:boolean;albumOptions?:RelationOption[];tagOptions?:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;onalbumsearch?:(value:string)=>void;ontagsearch?:(value:string)=>void;onalbumloadmore?:()=>void;ontagloadmore?:()=>void;onclose:()=>void;onapply:()=>void}=$props();
  let seq=$state(maxAssetSearchId(rules,groups));
  const expression=$derived(assetExpressionText(rules,groups,logic,negated));
  const ruleCount=$derived(rules.length+assetRuleCount(groups));
  const groupCount=$derived(assetGroupCount(groups));
  function nextId(){return++seq}
  function addRule(){rules=[...rules,{id:nextId(),field:'filename',op:'contains',value:''}]}
  function changeRule(next:AssetRule){rules=rules.map((rule)=>rule.id===next.id?next:rule)}
  function removeRule(id:number){rules=rules.filter((rule)=>rule.id!==id)}
  function addGroup(){groups=[...groups,{id:nextId(),logic:'AND',negated:false,rules:[{id:nextId(),field:'tag',op:'is',value:''}],groups:[]}]}
  function changeGroup(next:AssetGroup){groups=groups.map((group)=>group.id===next.id?next:group)}
  function reset(){rules=[];groups=[];logic='AND';negated=false}
</script>

<button type="button" class="v2-drawer-backdrop" aria-label="Close expert search editor" onclick={onclose}></button>
<aside class="v2-drawer">
  <div class="v2-drawer-head"><div><h2>Build asset search expression</h2><p class="v2-muted">Edit the draft here. Results change only when you apply/search.</p></div><V2Button onclick={onclose}>✕</V2Button></div>
  <div class="v2-drawer-body">
    <V2Section title="Expression structure"><V2Stack gap="md">
      <V2Card><V2Stack gap="sm"><V2Inline justify="between" wrap><V2Inline gap="sm"><V2Badge text="Root group"/><V2Segmented items={['AND','OR']} active={logic} onselect={(value)=>logic=value as 'AND'|'OR'} ariaLabel="Root group logic"/><V2Checkbox label="NOT group" checked={negated} onchange={(checked)=>negated=checked}/></V2Inline></V2Inline>
        {#each rules as rule (rule.id)}<V2AssetSearchRule idPrefix="expert-root" {rule} {albumOptions} {tagOptions} {albumLoading} {tagLoading} {albumHasMore} {tagHasMore} {onalbumsearch} {ontagsearch} {onalbumloadmore} {ontagloadmore} onchange={changeRule} onremove={()=>removeRule(rule.id)} onapply={onapply}/>{/each}
        {#each groups as group (group.id)}<V2AssetSearchGroup {group} {albumOptions} {tagOptions} {albumLoading} {tagLoading} {albumHasMore} {tagHasMore} {onalbumsearch} {ontagsearch} {onalbumloadmore} {ontagloadmore} {nextId} onchange={changeGroup} onremove={()=>groups=groups.filter((item)=>item.id!==group.id)} onapply={onapply}/>{/each}
        <V2Inline gap="sm" wrap><V2Button onclick={addRule}>+ Rule</V2Button><V2Button onclick={addGroup}>+ Nested group</V2Button></V2Inline>
      </V2Stack></V2Card>
    </V2Stack></V2Section>
    <V2Section title="Expression preview"><div class="v2-expression">{expression}</div></V2Section>
  </div>
  <div class="v2-drawer-foot"><V2Badge text={`${ruleCount} rules · ${groupCount} groups`}/><V2Inline gap="sm"><V2Button onclick={reset}>Reset</V2Button><V2Button onclick={onclose}>Cancel</V2Button><V2Button variant="primary" onclick={onapply}>Apply & Search</V2Button></V2Inline></div>
</aside>
