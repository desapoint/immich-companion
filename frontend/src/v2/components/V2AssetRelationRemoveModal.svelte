<script lang="ts">
  import SelectField from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Stack from './V2Stack.svelte';
  import type { AssetRelationshipOption } from '../data/contracts';

  let {
    kind,
    selectedCount,
    values = [],
    options,
    loading = false,
    busy = false,
    error = '',
    onvalueschange,
    onclose,
    onapply,
  }: {
    kind: 'album' | 'tags';
    selectedCount: number;
    values?: string[];
    options: AssetRelationshipOption[];
    loading?: boolean;
    busy?: boolean;
    error?: string;
    onvalueschange: (values: string[]) => void;
    onclose: () => void;
    onapply: () => void;
  } = $props();

  const noun = $derived(kind === 'album' ? 'albums' : 'tags');
</script>

<V2Modal
  id={`asset-remove-${kind}`}
  title={`Remove ${noun}`}
  description={`Choose ${noun} to remove from ${selectedCount.toLocaleString()} selected asset${selectedCount === 1 ? '' : 's'}. Assets without a chosen relationship are skipped.`}
  size="md"
  {onclose}
>
  <V2Stack gap="md">
    <SelectField
      id={`asset-remove-${kind}-options`}
      label={kind === 'album' ? 'Albums linked to selection' : 'Tags linked to selection'}
      multiple
      {values}
      {options}
      searchable
      allowEmpty
      placeholder={loading ? `Loading linked ${noun}…` : `Choose ${noun}…`}
      disabled={loading || options.length === 0}
      {onvalueschange}
    />
    {#if error}<p class="v2-small relation-remove-error">{error}</p>
    {:else if !loading && options.length === 0}<p class="v2-small v2-muted">No linked {noun} are available for this selection.</p>{/if}
  </V2Stack>
  {#snippet footer()}
    <V2Button disabled={busy} onclick={onclose}>Cancel</V2Button>
    <V2Button variant="danger" disabled={busy || loading || values.length === 0} onclick={onapply}>{busy ? 'Removing…' : `Remove selected ${noun}`}</V2Button>
  {/snippet}
</V2Modal>

<style>.relation-remove-error{color:var(--v2-danger,#e05a5a);margin:0}</style>
