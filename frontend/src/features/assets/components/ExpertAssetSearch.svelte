<script lang="ts">
  import type { AlbumOption, SearchGroup, TagOption } from '../types/assets';
  import AssetSearchFormHeader from './AssetSearchFormHeader.svelte';
  import SearchExpressionBuilder from './SearchExpressionBuilder.svelte';

  interface Props {
    expression: SearchGroup;
    albums: AlbumOption[];
    tags: TagOption[];
    disabled?: boolean;
    onsearch: () => void;
    onreset: () => void;
  }

  let { expression, albums, tags, disabled = false, onsearch, onreset }: Props = $props();

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onsearch();
  }
</script>

<form aria-label="Expert Immich asset search" onsubmit={submit}>
  <AssetSearchFormHeader
    eyebrow="Expert search"
    title="Build boolean relation and metadata rules"
    description="Combine conditions with AND or OR, use multi-value album and tag rules, nest groups, and negate any whole group."
    {disabled}
    {onreset}
  />

  <SearchExpressionBuilder {expression} {albums} {tags} {disabled} />
</form>

<style>
  form {
    display: grid;
    gap: 0.85rem;
  }
</style>
