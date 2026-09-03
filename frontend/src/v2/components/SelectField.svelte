<script lang="ts">
  export type SelectOption = string | { value: string; label: string; disabled?: boolean };

  let {
    label = '',
    value = $bindable<string | number>(''),
    options,
    width = 'full',
    disabled = false,
    ariaLabel,
    onchange,
  }: {
    label?: string;
    value?: string | number;
    options: SelectOption[];
    width?: 'full' | 'content';
    disabled?: boolean;
    ariaLabel?: string;
    onchange?: (value: string) => void;
  } = $props();

  const optionValue = (option: SelectOption) => typeof option === 'string' ? option : option.value;
  const optionLabel = (option: SelectOption) => typeof option === 'string' ? option : option.label;
  const optionDisabled = (option: SelectOption) => typeof option === 'string' ? false : Boolean(option.disabled);

  function handleChange(event: Event): void {
    const next = (event.currentTarget as HTMLSelectElement).value;
    value = next;
    onchange?.(next);
  }
</script>

<label class="v2-select-field" data-width={width}>
  {#if label}<span class="v2-field-label">{label}</span>{/if}
  <select
    class="v2-select-control"
    value={String(value)}
    {disabled}
    aria-label={ariaLabel || label || undefined}
    onchange={handleChange}
  >
    {#each options as option}
      <option value={optionValue(option)} disabled={optionDisabled(option)}>{optionLabel(option)}</option>
    {/each}
  </select>
</label>
