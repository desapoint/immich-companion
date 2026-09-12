<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Modal from './V2Modal.svelte';

  let {
    selectedCount,
    allMatching = false,
    pending = false,
    error = '',
    onkeep,
    onclear,
    onclose,
  }: {
    selectedCount: number;
    allMatching?: boolean;
    pending?: boolean;
    error?: string;
    onkeep: () => void;
    onclear: () => void;
    onclose: () => void;
  } = $props();
</script>

<V2Modal id="asset-search-selection" title="Keep selected assets?" size="sm" dismissOnBackdrop={!pending} onclose={onclose}>
  <div class="v2-search-selection-copy">
    <p>
      {selectedCount.toLocaleString()} asset{selectedCount === 1 ? ' is' : 's are'} selected.
      Choose whether that selection should remain available for bulk actions after applying the new search.
    </p>
    {#if allMatching}
      <p class="v2-small v2-muted">
        Keeping it will preserve the exact assets matched by the current search, including your exclusions. The new search will not redefine the selection.
      </p>
    {/if}
    {#if error}<p class="v2-search-selection-error" role="alert">{error}</p>{/if}
  </div>

  {#snippet footer()}
    <V2Button disabled={pending} onclick={onclose}>Cancel</V2Button>
    <V2Button disabled={pending} onclick={onclear}>Clear selection &amp; search</V2Button>
    <V2Button variant="primary" disabled={pending} onclick={onkeep}>{pending ? 'Preparing selection…' : 'Keep selection & search'}</V2Button>
  {/snippet}
</V2Modal>

<style>
  .v2-search-selection-copy { display:grid; gap:10px; }
  p { margin:0; line-height:1.5; }
  .v2-search-selection-error { color:var(--v2-red); }
</style>
