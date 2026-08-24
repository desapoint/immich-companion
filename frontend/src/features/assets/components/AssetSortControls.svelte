<script lang="ts">
  import SelectField, { type SelectOption } from '../../../lib/components/ui/SelectField.svelte';
  import type { AssetSort, AssetSortDirection, AssetSortField } from '../types/assets';

  interface Props {
    sort: AssetSort;
    disabled?: boolean;
    onchange: (sort: AssetSort) => void;
  }

  let { sort, disabled = false, onchange }: Props = $props();

  const fieldOptions: SelectOption[] = [
    { value: 'taken_at', label: 'Date taken' },
    { value: 'filename', label: 'Filename' },
    { value: 'created_at', label: 'Date added' },
    { value: 'modified_at', label: 'Last modified' },
    { value: 'width', label: 'Width' },
    { value: 'height', label: 'Height' },
  ];

  function directionOptions(field: AssetSortField): SelectOption[] {
    if (field === 'filename') {
      return [
        { value: 'asc', label: 'A to Z' },
        { value: 'desc', label: 'Z to A' },
      ];
    }
    if (field === 'width' || field === 'height') {
      return [
        { value: 'desc', label: 'Largest first' },
        { value: 'asc', label: 'Smallest first' },
      ];
    }
    return [
      { value: 'desc', label: 'Newest first' },
      { value: 'asc', label: 'Oldest first' },
    ];
  }
</script>

<section class="sort-controls" aria-label="Search result order">
  <div class="sort-copy">
    <span>Result order</span>
    <small>Applied before pagination</small>
  </div>
  <SelectField
    id="asset-sort-field"
    label="Sort by"
    value={sort.field}
    options={fieldOptions}
    {disabled}
    compact
    onchange={(field) => onchange({ ...sort, field: field as AssetSortField })}
  />
  <SelectField
    id="asset-sort-direction"
    label="Direction"
    value={sort.direction}
    options={directionOptions(sort.field)}
    {disabled}
    compact
    onchange={(direction) => onchange({
      ...sort,
      direction: direction as AssetSortDirection,
    })}
  />
</section>

<style>
  .sort-controls {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) minmax(10rem, 0.8fr) minmax(10rem, 0.8fr);
    align-items: start;
    gap: 0.65rem;
    padding: 0.65rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    background: var(--color-surface-soft);
  }

  .sort-copy {
    display: grid;
    align-self: center;
    gap: 0.14rem;
  }

  .sort-copy span {
    color: var(--color-ink-strong);
    font-size: 0.75rem;
    font-weight: 800;
  }

  .sort-copy small {
    color: var(--color-ink-muted);
    font-size: 0.66rem;
  }

  @media (max-width: 46rem) {
    .sort-controls {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .sort-copy {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 30rem) {
    .sort-controls {
      grid-template-columns: 1fr;
    }

    .sort-copy {
      grid-column: auto;
    }
  }
</style>
