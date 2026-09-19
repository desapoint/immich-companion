<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Field from './V2Field.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Stack from './V2Stack.svelte';

  let {
    title = 'Save search',
    name = '',
    description = '',
    busy = false,
    onclose,
    onsave,
  }: {
    title?: string;
    name?: string;
    description?: string;
    busy?: boolean;
    onclose: () => void;
    onsave: (name: string, description: string) => void;
  } = $props();

  let draftName = $derived(name);
  let draftDescription = $derived(description);
</script>

<V2Modal id="saved-search-editor" {title} description="Store the current asset search criteria in the active data source." size="md" {onclose}>
  <V2Stack gap="md">
    <V2Field label="Name" value={draftName} placeholder="Search name" disabled={busy} onchange={(value)=>draftName=value}/>
    <V2Field label="Description" value={draftDescription} placeholder="Optional description" multiline disabled={busy} onchange={(value)=>draftDescription=value}/>
  </V2Stack>
  {#snippet footer()}
    <V2Button disabled={busy} onclick={onclose}>Cancel</V2Button>
    <V2Button variant="primary" disabled={busy || !draftName.trim()} onclick={()=>onsave(draftName.trim(),draftDescription.trim())}>{busy?'Saving…':'Save'}</V2Button>
  {/snippet}
</V2Modal>
