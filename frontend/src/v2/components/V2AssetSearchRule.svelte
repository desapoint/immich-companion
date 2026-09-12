<script lang="ts">
  import DateTimePickerField from './DateTimePickerField.svelte';
  import SelectField from './SelectField.svelte';
  import V2AspectRatioField from './V2AspectRatioField.svelte';
  import V2Button from './V2Button.svelte';
  import { assetFieldSelectOptions,assetOperatorOptionsForField,splitAssetIds,type AssetRule } from '../state/assetSearch';
  import type { RelationOption } from '../data/contracts';

  let { idPrefix,rule,albumOptions=[],tagOptions=[],albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,onchange,onremove,onapply }:{idPrefix:string;rule:AssetRule;albumOptions?:RelationOption[];tagOptions?:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;onalbumsearch?:(value:string)=>void;ontagsearch?:(value:string)=>void;onalbumloadmore?:()=>void;ontagloadmore?:()=>void;onchange:(rule:AssetRule)=>void;onremove:()=>void;onapply:()=>void}=$props();

  const relationValues=$derived(splitAssetIds(rule.value));
  const relationOptions=$derived(rule.field==='album'?albumOptions:tagOptions);
  const relationLoading=$derived(rule.field==='album'?albumLoading:tagLoading);
  const relationHasMore=$derived(rule.field==='album'?albumHasMore:tagHasMore);
  const relationSearch=$derived(rule.field==='album'?onalbumsearch:ontagsearch);
  const relationLoadMore=$derived(rule.field==='album'?onalbumloadmore:ontagloadmore);

  function update(patch:Partial<AssetRule>){onchange({...rule,...patch})}
  function changeField(value:string){update({field:value,op:assetOperatorOptionsForField(value)[0]?.value??'is',value:''})}
  function changeOperator(value:string){update({op:value,...(value==='hasNone'?{value:''}:{})})}
  function handleKeydown(event:KeyboardEvent){if(event.key!=='Enter'||event.isComposing)return;event.preventDefault();onapply()}
</script>

<div class="v2-expert-rule" data-field={rule.field}>
  <SelectField id={`${idPrefix}-field-${rule.id}`} value={rule.field} options={assetFieldSelectOptions} searchable searchPlaceholder="Find a field…" onchange={changeField}/>
  <SelectField id={`${idPrefix}-op-${rule.id}`} value={rule.op} options={assetOperatorOptionsForField(rule.field)} onchange={changeOperator}/>

  {#if rule.op==='hasNone'}
    <span class="v2-expert-rule-empty v2-small v2-muted">No {rule.field==='album'?'album':'tag'} membership</span>
  {:else if rule.field==='album'||rule.field==='tag'}
    <SelectField
      id={`${idPrefix}-value-${rule.id}`}
      multiple
      values={relationValues}
      searchable
      allowEmpty
      placeholder={`Choose ${rule.field==='album'?'albums':'tags'}…`}
      options={relationOptions}
      loading={relationLoading}
      hasMore={relationHasMore}
      onsearchchange={relationSearch}
      onloadmore={relationLoadMore}
      onvalueschange={(values)=>update({value:values.join(',')})}
    />
  {:else if rule.field==='mediaType'}
    <SelectField
      id={`${idPrefix}-value-${rule.id}`}
      value={rule.value}
      allowEmpty
      placeholder="Choose media type…"
      options={[
        {value:'Image',label:'Image'},
        {value:'Video',label:'Video'},
        {value:'Audio',label:'Audio'},
        {value:'Other',label:'Other'},
      ]}
      onchange={(value)=>update({value})}
    />
  {:else if rule.field==='favorite'||rule.field==='archived'}
    <SelectField
      id={`${idPrefix}-value-${rule.id}`}
      value={rule.value}
      allowEmpty
      placeholder="Choose state…"
      options={[{value:'true',label:'Yes'},{value:'false',label:'No'}]}
      onchange={(value)=>update({value})}
    />
  {:else if rule.field==='stackMembership'}
    <SelectField
      id={`${idPrefix}-value-${rule.id}`}
      value={rule.value}
      allowEmpty
      placeholder="Choose stack state…"
      options={[{value:'true',label:'In a stack'},{value:'false',label:'Not in a stack'}]}
      onchange={(value)=>update({value})}
    />
  {:else if rule.field==='stackRole'}
    <SelectField
      id={`${idPrefix}-value-${rule.id}`}
      value={rule.value}
      allowEmpty
      placeholder="Choose stack role…"
      options={[{value:'true',label:'Primary asset'},{value:'false',label:'Secondary member'}]}
      onchange={(value)=>update({value})}
    />
  {:else if rule.field==='takenDate'}
    <DateTimePickerField id={`${idPrefix}-value-${rule.id}`} value={rule.value} onchange={(value)=>update({value})}/>
  {:else if rule.field==='aspectRatio'}
    <V2AspectRatioField id={`${idPrefix}-value-${rule.id}`} label="" value={rule.value} onchange={(value)=>update({value})}/>
  {:else}
    <input
      id={`${idPrefix}-value-${rule.id}`}
      type={rule.field==='filename'?'text':'number'}
      min={rule.field==='filename'?undefined:'0'}
      step={rule.field==='filename'?undefined:'1'}
      value={rule.value}
      placeholder={rule.field==='filename'?'Value…':'0'}
      aria-label={`${rule.field} value`}
      oninput={(event)=>update({value:event.currentTarget.value})}
      onkeydown={handleKeydown}
    >
  {/if}
  <V2Button ariaLabel="Remove rule" title="Remove rule" onclick={onremove}>✕</V2Button>
</div>

<style>
  .v2-expert-rule-empty{display:flex;align-items:center;min-height:2.25rem;padding-inline:.65rem;border:1px dashed var(--v2-line);border-radius:.45rem}
  .v2-expert-rule :global(.v2-aspect-ratio-field>.v2-field-label:empty){display:none}
</style>
