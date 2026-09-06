<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Field from './V2Field.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Stack from './V2Stack.svelte';

  let {
    id,
    noun,
    initialName = '',
    busy = false,
    error = '',
    onclose,
    oncreate,
  }: {
    id: string;
    noun: string;
    initialName?: string;
    busy?: boolean;
    error?: string;
    onclose: () => void;
    oncreate: (name: string) => void;
  } = $props();

  let name = $state(initialName);
</script>

<V2Modal {id} title={`Create ${noun}`} description={`Add a new ${noun} to the current data source.`} size="sm" {onclose}>
  <V2Stack gap="md">
    <V2Field label="Title" value={name} disabled={busy} onchange={(value) => name = value}/>
    {#if error}<div class="v2-small v2-create-named-error">{error}</div>{/if}
  </V2Stack>
  {#snippet footer()}
    <V2Button disabled={busy} onclick={onclose}>Cancel</V2Button>
    <V2Button variant="primary" disabled={busy || !name.trim()} onclick={() => oncreate(name.trim())}>{busy ? 'Creating…' : `Create ${noun}`}</V2Button>
  {/snippet}
</V2Modal>

<style>
  .v2-create-named-error { color:var(--v2-danger, #e05a5a); }
</style>
