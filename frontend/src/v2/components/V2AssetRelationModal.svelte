<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Stack from './V2Stack.svelte';
  import type { RelationOption } from '../data/contracts';

  let { kind,selectedCount,albumValue='',tagValues=[],albumOptions,tagOptions,albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,busy=false,onalbumchange,ontagschange,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,onclose,onapply }:{
    kind:'album'|'tags';selectedCount:number;albumValue?:string;tagValues?:string[];albumOptions:RelationOption[];tagOptions:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;busy?:boolean;
    onalbumchange:(value:string)=>void;ontagschange:(values:string[])=>void;onalbumsearch:(value:string)=>void;ontagsearch:(value:string)=>void;onalbumloadmore:()=>void;ontagloadmore:()=>void;onclose:()=>void;onapply:()=>void;
  }=$props();
</script>

<V2Modal id="asset-relation-action" title={kind==='album'?'Add selected assets to album':'Add tags to selected assets'} description={`${selectedCount.toLocaleString()} selected asset${selectedCount===1?'':'s'}`} size="md" {onclose}>
  <V2Stack gap="md">
    {#if kind==='album'}
      <SelectField id="asset-action-album" label="Album" value={albumValue} options={albumOptions} searchable allowEmpty placeholder="Choose album…" loading={albumLoading} hasMore={albumHasMore} onchange={onalbumchange} onsearchchange={onalbumsearch} onloadmore={onalbumloadmore}/>
    {:else}
      <SelectField id="asset-action-tags" label="Tags" multiple values={tagValues} options={tagOptions} searchable allowEmpty placeholder="Choose tags…" loading={tagLoading} hasMore={tagHasMore} onvalueschange={ontagschange} onsearchchange={ontagsearch} onloadmore={ontagloadmore}/>
    {/if}
  </V2Stack>
  {#snippet footer()}<V2Button onclick={onclose}>Cancel</V2Button><V2Button variant="primary" disabled={busy||(kind==='album'?!albumValue:tagValues.length===0)} onclick={onapply}>{busy?'Applying…':'Apply'}</V2Button>{/snippet}
</V2Modal>
