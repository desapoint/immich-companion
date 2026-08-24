<script lang="ts">
  import type { AlbumOption, SearchGroup } from '../types/assets';
  import AssetSearchFormHeader from './AssetSearchFormHeader.svelte';
  import SearchExpressionBuilder from './SearchExpressionBuilder.svelte';

  interface Props {
    expression: SearchGroup;
    albums: AlbumOption[];
    disabled?: boolean;
    onsearch: () => void;
    onreset: () => void;
  }

  let { expression, albums, disabled = false, onsearch, onreset }: Props = $props();

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onsearch();
  }
</script>

<form aria-label="Advanced Immich asset search" onsubmit={submit}>
  <AssetSearchFormHeader
    eyebrow="Advanced search"
    title="Build album and metadata rules"
    description="Combine conditions with AND or OR, nest groups, and negate any whole group."
    {disabled}
    {onreset}
  />

  <SearchExpressionBuilder {expression} {albums} {disabled} />
</form>

<style>
  form {
    display: grid;
    gap: 0.85rem;
  }

</style>
