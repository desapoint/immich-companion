<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import { assetFieldSelectOptions,assetOperatorOptionsForField,type AssetRule } from '../state/assetSearch';
  import type { RelationOption } from '../data/contracts';

  let { idPrefix,rule,albumOptions=[],tagOptions=[],albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,onchange,onremove,onapply }:{idPrefix:string;rule:AssetRule;albumOptions?:RelationOption[];tagOptions?:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;onalbumsearch?:(value:string)=>void;ontagsearch?:(value:string)=>void;onalbumloadmore?:()=>void;ontagloadmore?:()=>void;onchange:(rule:AssetRule)=>void;onremove:()=>void;onapply:()=>void}=$props();

  function update(patch:Partial<AssetRule>){onchange({...rule,...patch})}
  function changeField(value:string){update({field:value,op:assetOperatorOptionsForField(value)[0]?.value??'is',value:''})}
  function changeOperator(value:string){update({op:value,...(value==='hasNone'?{value:''}:{})})}
  function handleKeydown(event:KeyboardEvent){if(event.key!=='Enter'||event.isComposing)return;event.preventDefault();onapply()}
</script>

<div class="v2-expert-rule">
  <SelectField id={`${idPrefix}-field-${rule.id}`} value={rule.field} options={assetFieldSelectOptions} onchange={changeField}/>
  <SelectField id={`${idPrefix}-op-${rule.id}`} value={rule.op} options={assetOperatorOptionsForField(rule.field)} onchange={changeOperator}/>
  {#if rule.op==='hasNone'}
    <span class="v2-expert-rule-empty v2-small v2-muted">No value required</span>
  {:else if rule.field==='album'||rule.field==='tag'}
    <SelectField id={`${idPrefix}-value-${rule.id}`} value={rule.value} searchable allowEmpty placeholder={`Choose ${rule.field}…`} options={rule.field==='album'?albumOptions:tagOptions} loading={rule.field==='album'?albumLoading:tagLoading} hasMore={rule.field==='album'?albumHasMore:tagHasMore} onsearchchange={rule.field==='album'?onalbumsearch:ontagsearch} onloadmore={rule.field==='album'?onalbumloadmore:ontagloadmore} onchange={(value)=>update({value})}/>
  {:else}
    <input value={rule.value} placeholder="Value…" oninput={(event)=>update({value:event.currentTarget.value})} onkeydown={handleKeydown}>
  {/if}
  <V2Button ariaLabel="Remove rule" title="Remove rule" onclick={onremove}>✕</V2Button>
</div>

<style>.v2-expert-rule-empty{display:flex;align-items:center;min-height:2.25rem;padding-inline:.65rem;border:1px dashed var(--v2-line);border-radius:.45rem}</style>
