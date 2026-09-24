<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import ColorField from '../../../lib/components/ui/ColorField.svelte';
  import V2ColorSwatch from '../../../lib/components/ui/ColorSwatch.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import V2Modal from '../../../lib/components/ui/Modal.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import { errorMessage } from '../../../lib/api/mutationFeedback';
  import type { RelationOption } from '../../../lib/types/libraryContracts';

  export type AlbumCreateDetails = { name:string; description:string };
  export type TagCreateDetails = { name:string; color:string|null; parentId:string };

  let {
    kind,
    initialName = '',
    busy = false,
    onclose,
    oncreatealbum,
    oncreatetag,
    oncreated,
  }: {
    kind:'album'|'tag';
    initialName?:string;
    busy?:boolean;
    onclose:()=>void;
    oncreatealbum?:(input:AlbumCreateDetails)=>Promise<RelationOption>;
    oncreatetag?:(input:TagCreateDetails)=>Promise<RelationOption>;
    oncreated:(option:RelationOption)=>Promise<void>|void;
  }=$props();

  let name=$derived(initialName);
  let description=$state('');
  let color=$state<string|null>('#9A78FF');
  let parentId=$state('');
  let parentOptions=$state<Array<{value:string;label:string;subtitle?:string}>>([]);
  let saving=$state(false);
  let loadError=$state('');
  const parentPath=$derived(parentOptions.find((option)=>option.value===parentId)?.label??'');

  async function loadParentOptions(){
    if(kind!=='tag')return;
    try{parentOptions=await libraryData.tags.parentOptions();loadError=''}catch(error){loadError=errorMessage(error,'Parent tag options could not be loaded.')}
  }

  async function defaultCreateAlbum(input:AlbumCreateDetails):Promise<RelationOption>{
    const created=await libraryData.albums.create(input.name,input.description);
    if(!created)throw new Error('The album was not created.');
    return{value:created.id,label:created.album_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
  }

  async function defaultCreateTag(input:TagCreateDetails):Promise<RelationOption>{
    const created=await libraryData.tags.create(input.name,input.color,input.parentId);
    if(!created)throw new Error('The tag was not created.');
    return{value:created.id,label:created.tag_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
  }

  async function save(){
    if(!name.trim()||saving||busy)return;
    saving=true;loadError='';
    try{
      const option=kind==='album'
        ?await(oncreatealbum??defaultCreateAlbum)({name:name.trim(),description})
        :await(oncreatetag??defaultCreateTag)({name:name.trim(),color,parentId});
      await oncreated(option);
    }catch(error){loadError=errorMessage(error,`The ${kind} could not be created.`)}finally{saving=false}
  }

  $effect(()=>{if(kind==='tag')void loadParentOptions()});
</script>

<V2Modal id={`asset-create-${kind}`} title={`Create ${kind}`} description={kind==='album'?'Add an album to the current data source.':'Create a tag with an optional parent.'} size="md" {onclose}>
  <V2Stack gap="md">
    <V2Field label="Name" value={name} disabled={saving||busy} onvalueinput={(value)=>name=value}/>
    {#if kind==='album'}
      <V2Field label="Description" value={description} multiline={true} disabled={saving||busy} onchange={(value)=>description=value}/>
    {:else}
      <ColorField id="asset-create-tag-color" label="Color" value={color} disabled={saving||busy} onchange={(value)=>color=value}/>
      <SelectField id="asset-create-tag-parent" label="Parent" value={parentId} options={parentOptions} allowEmpty searchable searchPlaceholder="Search parent tags or paths…" placeholder="No parent — root tag" disabled={saving||busy} onchange={(value)=>parentId=value}/>
      <V2Section title="Hierarchy preview"><V2Card><span class="create-tag-preview"><V2ColorSwatch {color} size="sm"/><span class="v2-small">{parentPath?`${parentPath} / ${name||'New tag'}`:name||'Root tag'}</span></span></V2Card></V2Section>
    {/if}
    {#if loadError}<div class="v2-small create-error">{loadError}</div>{/if}
  </V2Stack>
  {#snippet footer()}
    <V2Button disabled={saving||busy} onclick={onclose}>Cancel</V2Button>
    <V2Button variant="primary" disabled={saving||busy||!name.trim()} onclick={()=>void save()}>{saving?'Creating…':`Create ${kind}`}</V2Button>
  {/snippet}
</V2Modal>

<style>.create-error{color:var(--v2-danger,#e05a5a)}.create-tag-preview{display:inline-flex;align-items:center;gap:8px;min-width:0}</style>
