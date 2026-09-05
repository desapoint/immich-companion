<script lang="ts">
  import SelectField, { type SelectOption } from './SelectField.svelte';
  import V2Segmented from './V2Segmented.svelte';

  export type SortField = { value: string; label: string };
  export type ResultMode = 'Pagination' | 'Infinite';

  let {
    id,
    sort,
    sortFields,
    pageSize,
    pageSizes = [24, 48, 96],
    resultMode,
    batchLabel = 'batch',
    onsort,
    onpagesize,
    onmode,
  }: {
    id: string;
    sort: string;
    sortFields: SortField[];
    pageSize: number;
    pageSizes?: number[];
    resultMode: ResultMode;
    batchLabel?: string;
    onsort?: (value: string) => void;
    onpagesize?: (value: number) => void;
    onmode?: (mode: ResultMode) => void;
  } = $props();

  const sortOptions = $derived<SelectOption[]>(sortFields.flatMap((field) => [
    { value: `${field.value}:asc`, label: field.label, direction: 'asc' },
    { value: `${field.value}:desc`, label: field.label, direction: 'desc' },
  ]));
  const sizeOptions = $derived(pageSizes.map((size) => ({ value: String(size), label: `${size} / ${batchLabel}` })));
</script>

<div class="v2-collection-controls">
  <SelectField
    id={`${id}-sort`}
    width="content"
    value={sort}
    options={sortOptions}
    onchange={onsort}
  />
  <SelectField
    id={`${id}-page-size`}
    width="content"
    value={pageSize}
    options={sizeOptions}
    onchange={(value) => onpagesize?.(Number(value))}
  />
  <V2Segmented
    items={['Pagination','Infinite']}
    active={resultMode}
    onselect={(value) => onmode?.(value as ResultMode)}
    ariaLabel="Result loading mode"
  />
</div>
