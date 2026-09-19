<script lang="ts">
  import SelectField, { type SelectOption } from './SelectField.svelte';
  import V2Button from './V2Button.svelte';

  let {
    id,
    label,
    values = [],
    options,
    emptySelected = false,
    emptyLabel,
    placeholder,
    loading = false,
    hasMore = false,
    onvalueschange,
    onemptychange,
    onsearchchange,
    onloadmore,
  }: {
    id: string;
    label: string;
    values?: string[];
    options: SelectOption[];
    emptySelected?: boolean;
    emptyLabel: string;
    placeholder: string;
    loading?: boolean;
    hasMore?: boolean;
    onvalueschange?: (values: string[]) => void;
    onemptychange?: (selected: boolean) => void;
    onsearchchange?: (query: string) => void;
    onloadmore?: () => void;
  } = $props();

  function setValues(next: string[]): void {
    if (next.length > 0 && emptySelected) onemptychange?.(false);
    onvalueschange?.(next);
  }

  function toggleEmpty(): void {
    const next = !emptySelected;
    if (next && values.length > 0) onvalueschange?.([]);
    onemptychange?.(next);
  }
</script>

<div class="v2-relation-filter-field">
  <SelectField
    {id}
    {label}
    multiple
    searchable
    allowEmpty
    {values}
    {options}
    {placeholder}
    {loading}
    {hasMore}
    {onsearchchange}
    {onloadmore}
    searchPlaceholder={`Search ${label.toLocaleLowerCase()}…`}
    onvalueschange={setValues}
  />
  <V2Button active={emptySelected} ariaLabel={emptyLabel} title={emptyLabel} onclick={toggleEmpty}>{emptyLabel}</V2Button>
</div>

<style>
  .v2-relation-filter-field {
    display:grid;
    grid-template-columns:minmax(0,1fr) auto;
    align-items:end;
    gap:.55rem;
  }

  .v2-relation-filter-field :global(.v2-button) {
    white-space:nowrap;
  }

  @media (max-width: 34rem) {
    .v2-relation-filter-field { grid-template-columns:1fr; align-items:stretch; }
    .v2-relation-filter-field :global(.v2-button) { width:100%; }
  }
</style>
