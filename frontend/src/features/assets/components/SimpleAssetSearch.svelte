<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type {
    AssetType,
    SearchBooleanFilter,
    SimpleAssetSearchFilters,
  } from '../types/assets';
  import AssetSearchFormHeader from './AssetSearchFormHeader.svelte';
  import SimpleAdvancedFilters from './SimpleAdvancedFilters.svelte';

  interface Props {
    filters: SimpleAssetSearchFilters;
    disabled?: boolean;
    onchange: (filters: SimpleAssetSearchFilters) => void;
    onsearch: () => void;
    onreset: () => void;
  }

  let { filters, disabled = false, onchange, onsearch, onreset }: Props = $props();

  const stateOptions = [
    { value: 'any', label: 'Any' },
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ];

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onsearch();
  }
</script>

<form aria-label="Simple Immich asset search" onsubmit={submit}>
  <AssetSearchFormHeader
    eyebrow="Library search"
    title="Find assets quickly"
    description="Use flat filters for quick searches; open Advanced for dates and dimensions."
    {disabled}
    {onreset}
  />

  <div class="simple-fields">
    <label class="query-field">
      <span>Filename</span>
      <input
        type="search"
        value={filters.query}
        placeholder="Search by filename"
        {disabled}
        oninput={(event) => onchange({ ...filters, query: event.currentTarget.value })}
      />
    </label>
    <SelectField
      id="simple-search-type"
      label="Media type"
      value={filters.assetType}
      options={[
        { value: '', label: 'Any type' },
        { value: 'IMAGE', label: 'Image' },
        { value: 'VIDEO', label: 'Video' },
        { value: 'AUDIO', label: 'Audio' },
        { value: 'OTHER', label: 'Other' },
      ]}
      {disabled}
      onchange={(value) => onchange({ ...filters, assetType: value as '' | AssetType })}
    />
    <SelectField
      id="simple-search-favorite"
      label="Favorite"
      value={filters.favorite}
      options={stateOptions}
      {disabled}
      onchange={(value) => onchange({ ...filters, favorite: value as SearchBooleanFilter })}
    />
    <SelectField
      id="simple-search-archived"
      label="Archived"
      value={filters.archived}
      options={stateOptions}
      {disabled}
      onchange={(value) => onchange({ ...filters, archived: value as SearchBooleanFilter })}
    />
    <SelectField
      id="simple-search-trashed"
      label="Trashed"
      value={filters.trashed}
      options={stateOptions}
      {disabled}
      onchange={(value) => onchange({ ...filters, trashed: value as SearchBooleanFilter })}
    />
  </div>

  <SimpleAdvancedFilters {filters} {disabled} {onchange} />
</form>

<style>
  form {
    display: grid;
    gap: 0.9rem;
  }

  .simple-fields {
    display: grid;
    grid-template-columns: minmax(16rem, 2fr) repeat(4, minmax(7.5rem, 0.72fr));
    align-items: end;
    gap: 0.65rem;
  }

  .query-field {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .query-field > span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    letter-spacing: 0.045em;
  }

  input {
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
  }

  input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  input:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  @media (max-width: 75rem) {
    .simple-fields {
      grid-template-columns: minmax(14rem, 2fr) repeat(2, minmax(8rem, 1fr));
    }
  }

  @media (max-width: 46rem) {
    .simple-fields {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .query-field {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 30rem) {
    .simple-fields {
      grid-template-columns: 1fr;
    }

    .query-field {
      grid-column: auto;
    }
  }
</style>
