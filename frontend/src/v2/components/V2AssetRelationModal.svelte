<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import V2CreateNamedItemModal from './V2CreateNamedItemModal.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Stack from './V2Stack.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { RelationOption } from '../data/contracts';

  let { kind,selectedCount,albumValue='',tagValues=[],albumOptions,tagOptions,albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,busy=false,onalbumchange,ontagschange,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,onclose,onapply }:{
    kind:'album'|'tags';selectedCount:number;albumValue?:string;tagValues?:string[];albumOptions:RelationOption[];tagOptions:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;busy?:boolean;
    onalbumchange:(value:string)=>void;ontagschange:(values:string[])=>void;onalbumsearch:(value:string)=>void;ontagsearch:(value:string)=>void;onalbumloadmore:()=>void;ontagloadmore:()=>void;onclose:()=>void;onapply:()=>void;
  }=$props();

  let createKind=$state<'album'|'tag'|null>(null);
  let createName=$state('');
  let createBusy=$state(false);
  let createError=$state('');
  let createdAlbums=$state<RelationOption[]>([]);
  let createdTags=$state<RelationOption[]>([]);
  const resolvedAlbumOptions=$derived([...new Map([...createdAlbums,...albumOptions].map((option)=>[option.value,option])).values()]);
  const resolvedTagOptions=$derived([...new Map([...createdTags,...tagOptions].map((option)=>[option.value,option])).values()]);

  function openCreate(next:'album'|'tag',query:string){createKind=next;createName=query;createError=''}
  function closeCreate(){if(createBusy)return;createKind=null;createName='';createError=''}
  async function createNamed(name:string){
    if(!createKind||createBusy)return;
    createBusy=true;createError='';
    try{
      if(createKind==='album'){
        const created=await libraryData.albums.create(name);
        if(!created)throw new Error('The album was not created.');
        const option={value:created.id,label:created.album_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
        createdAlbums=[option,...createdAlbums.filter((item)=>item.value!==option.value)];
        onalbumchange(option.value);
      }else{
        const created=await libraryData.tags.create(name);
        if(!created)throw new Error('The tag was not created.');
        const option={value:created.id,label:created.tag_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
        createdTags=[option,...createdTags.filter((item)=>item.value!==option.value)];
        ontagschange([...new Set([...tagValues,option.value])]);
      }
      createKind=null;createName='';
    }catch(error){createError=errorMessage(error,`The ${createKind} could not be created.`)}finally{createBusy=false}
  }
</script>

<V2Modal id="asset-relation-action" title={kind==='album'?'Add selected assets to album':'Add tags to selected assets'} description={`${selectedCount.toLocaleString()} selected asset${selectedCount===1?'':'s'}`} size="md" {onclose}>
  <V2Stack gap="md">
    {#if kind==='album'}
      <SelectField id="asset-action-album" label="Album" value={albumValue} options={resolvedAlbumOptions} searchable allowEmpty placeholder="Choose album…" loading={albumLoading} hasMore={albumHasMore} addLabel="Create album" onchange={onalbumchange} onsearchchange={onalbumsearch} onloadmore={onalbumloadmore} onadd={(query)=>openCreate('album',query)}/>
    {:else}
      <SelectField id="asset-action-tags" label="Tags" multiple values={tagValues} options={resolvedTagOptions} searchable allowEmpty placeholder="Choose tags…" loading={tagLoading} hasMore={tagHasMore} addLabel="Create tag" onvalueschange={ontagschange} onsearchchange={ontagsearch} onloadmore={ontagloadmore} onadd={(query)=>openCreate('tag',query)}/>
    {/if}
  </V2Stack>
  {#snippet footer()}<V2Button onclick={onclose}>Cancel</V2Button><V2Button variant="primary" disabled={busy||(kind==='album'?!albumValue:tagValues.length===0)} onclick={onapply}>{busy?'Applying…':'Apply'}</V2Button>{/snippet}
</V2Modal>

{#if createKind}
  <V2CreateNamedItemModal id={`asset-create-${createKind}`} noun={createKind} initialName={createName} busy={createBusy} error={createError} onclose={closeCreate} oncreate={(name)=>void createNamed(name)}/>
{/if}
