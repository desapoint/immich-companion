<script lang="ts">
  import SelectField, { type SelectAddRequest } from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2RelationCreateModal, { type AlbumCreateDetails, type TagCreateDetails } from './V2RelationCreateModal.svelte';
  import V2Stack from './V2Stack.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage } from '../data/mutationFeedback';
  import type { RelationOption } from '../data/contracts';

  let {
    kind,selectedCount,albumValue='',tagValues=[],albumOptions,tagOptions,albumLoading=false,tagLoading=false,albumHasMore=false,tagHasMore=false,busy=false,
    onalbumchange,ontagschange,onalbumsearch,ontagsearch,onalbumloadmore,ontagloadmore,oncreatealbum,oncreatetag,oncreated,onclose,onapply,
  }:{
    kind:'album'|'tags';selectedCount:number;albumValue?:string;tagValues?:string[];albumOptions:RelationOption[];tagOptions:RelationOption[];albumLoading?:boolean;tagLoading?:boolean;albumHasMore?:boolean;tagHasMore?:boolean;busy?:boolean;
    onalbumchange:(value:string)=>void;ontagschange:(values:string[])=>void;onalbumsearch:(value:string)=>void;ontagsearch:(value:string)=>void;onalbumloadmore:()=>void;ontagloadmore:()=>void;
    oncreatealbum?:(input:string|AlbumCreateDetails)=>Promise<RelationOption>;oncreatetag?:(input:string|TagCreateDetails)=>Promise<RelationOption>;oncreated:(kind:'album'|'tag',option:RelationOption)=>Promise<void>;onclose:()=>void;onapply:()=>void;
  }=$props();

  let createKind=$state<'album'|'tag'|null>(null);
  let createName=$state('');
  let createBusy=$state(false);
  let createError=$state('');
  let createdAlbums=$state<RelationOption[]>([]);
  let createdTags=$state<RelationOption[]>([]);
  const resolvedAlbumOptions=$derived([...new Map([...createdAlbums,...albumOptions].map((option)=>[option.value,option])).values()]);
  const resolvedTagOptions=$derived([...new Map([...createdTags,...tagOptions].map((option)=>[option.value,option])).values()]);

  async function defaultCreateAlbum(input:string|AlbumCreateDetails):Promise<RelationOption>{
    const details=typeof input==='string'?{name:input,description:''}:input;
    const created=await libraryData.albums.create(details.name.trim(),details.description);
    if(!created)throw new Error('The album was not created.');
    return{value:created.id,label:created.album_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
  }
  async function defaultCreateTag(input:string|TagCreateDetails):Promise<RelationOption>{
    const details=typeof input==='string'?{name:input,color:null,parentPath:''}:input;
    const created=await libraryData.tags.create(details.name.trim(),details.color,details.parentPath);
    if(!created)throw new Error('The tag was not created.');
    return{value:created.id,label:created.tag_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
  }

  async function finishCreated(createdKind:'album'|'tag',option:RelationOption){
    if(createdKind==='album'){
      createdAlbums=[option,...createdAlbums.filter((item)=>item.value!==option.value)];
      onalbumchange(option.value);
    }else{
      createdTags=[option,...createdTags.filter((item)=>item.value!==option.value)];
      ontagschange([...new Set([...tagValues,option.value])]);
    }
    await oncreated(createdKind,option);
    onclose();
  }

  async function quickCreate(createdKind:'album'|'tag',name:string){
    if(createBusy)return;
    if(!name.trim()){createError=`Type a ${createdKind} title before using Add, or hold Shift to open the full create dialog.`;return}
    createBusy=true;createError='';
    try{
      const option=createdKind==='album'
        ?await(oncreatealbum??defaultCreateAlbum)(name.trim())
        :await(oncreatetag??defaultCreateTag)(name.trim());
      await finishCreated(createdKind,option);
    }catch(error){createError=errorMessage(error,`The ${createdKind} could not be created and assigned.`)}finally{createBusy=false}
  }

  function handleAdd(createdKind:'album'|'tag',request:SelectAddRequest){
    if(request.shiftKey){createKind=createdKind;createName=request.query;createError='';return}
    void quickCreate(createdKind,request.query);
  }
</script>

<V2Modal id="asset-relation-action" title={kind==='album'?'Add selected assets to album':'Add tags to selected assets'} description={`${selectedCount.toLocaleString()} selected asset${selectedCount===1?'':'s'}`} size="md" {onclose}>
  <V2Stack gap="md">
    {#if kind==='album'}
      <SelectField id="asset-action-album" label="Album" value={albumValue} options={resolvedAlbumOptions} searchable allowEmpty placeholder="Choose album…" loading={albumLoading||createBusy} hasMore={albumHasMore} addLabel="Add album" onchange={onalbumchange} onsearchchange={onalbumsearch} onloadmore={onalbumloadmore} onadd={(request)=>handleAdd('album',request)}/>
    {:else}
      <SelectField id="asset-action-tags" label="Tags" multiple values={tagValues} options={resolvedTagOptions} searchable allowEmpty placeholder="Choose tags…" loading={tagLoading||createBusy} hasMore={tagHasMore} addLabel="Add tag" onvalueschange={ontagschange} onsearchchange={ontagsearch} onloadmore={ontagloadmore} onadd={(request)=>handleAdd('tag',request)}/>
    {/if}
    {#if createError}<div class="v2-small relation-create-error">{createError}</div>{/if}
  </V2Stack>
  {#snippet footer()}<V2Button disabled={createBusy} onclick={onclose}>Cancel</V2Button><V2Button variant="primary" disabled={busy||createBusy||(kind==='album'?!albumValue:tagValues.length===0)} onclick={onapply}>{busy?'Applying…':createBusy?'Creating…':'Apply'}</V2Button>{/snippet}
</V2Modal>

{#if createKind}
  <V2RelationCreateModal
    kind={createKind}
    initialName={createName}
    busy={busy}
    oncreatealbum={oncreatealbum ? (input)=>oncreatealbum(input) : undefined}
    oncreatetag={oncreatetag ? (input)=>oncreatetag(input) : undefined}
    oncreated={(option)=>finishCreated(createKind!,option)}
    onclose={()=>{if(!busy){createKind=null;createName=''}}}
  />
{/if}

<style>.relation-create-error{color:var(--v2-danger,#e05a5a)}</style>
