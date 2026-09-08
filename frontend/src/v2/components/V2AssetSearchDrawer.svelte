<script lang="ts">
  import { onMount, tick } from 'svelte';
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
  let drawerElement=$state<HTMLElement>();
  const expression=$derived(assetExpressionText(rules,groups,logic,negated));
  const ruleCount=$derived(rules.length+assetRuleCount(groups));
  const groupCount=$derived(assetGroupCount(groups));
  const focusableSelector='button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

  function nextId(){return++seq}
  function focusElement(id:string){void tick().then(()=>requestAnimationFrame(()=>document.getElementById(id)?.focus()))}
  function addRule(){const id=nextId();rules=[...rules,{id,field:'filename',op:'contains',value:''}];focusElement(`expert-root-field-${id}`)}
  function changeRule(next:AssetRule){rules=rules.map((rule)=>rule.id===next.id?next:rule)}
  function removeRule(id:number){rules=rules.filter((rule)=>rule.id!==id)}
  function addGroup(){const groupId=nextId(),ruleId=nextId();groups=[...groups,{id:groupId,logic:'AND',negated:false,rules:[{id:ruleId,field:'tag',op:'is',value:''}],groups:[]}];focusElement(`expert-group-${groupId}-field-${ruleId}`)}
  function changeGroup(next:AssetGroup){groups=groups.map((group)=>group.id===next.id?next:group)}
  function reset(){rules=[];groups=[];logic='AND';negated=false}
  function focusableElements(){return drawerElement?[...drawerElement.querySelectorAll<HTMLElement>(focusableSelector)].filter((element)=>element.getClientRects().length>0):[]}
  function handleDrawerKeydown(event:KeyboardEvent){
    if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onclose();return}
    if(event.key!=='Tab')return;
    const items=focusableElements();
    if(!items.length){event.preventDefault();drawerElement?.focus();return}
    const first=items[0],last=items[items.length-1],active=document.activeElement;
    if(event.shiftKey&&(active===first||!drawerElement?.contains(active))){event.preventDefault();last.focus()}
    else if(!event.shiftKey&&(active===last||!drawerElement?.contains(active))){event.preventDefault();first.focus()}
  }
  onMount(()=>{void tick().then(()=>requestAnimationFrame(()=>focusableElements()[0]?.focus()))});
</script>

<button type="button" class="v2-drawer-backdrop" aria-label="Close expert search editor" tabindex="-1" onclick={onclose}></button>
<aside bind:this={drawerElement} class="v2-drawer" role="dialog" aria-modal="true" aria-label="Expert asset search editor" tabindex="-1" onkeydown={handleDrawerKeydown}>
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
