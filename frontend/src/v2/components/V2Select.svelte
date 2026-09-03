<script lang="ts">
  type SelectOption = string | { value: string; label: string };

  let {
    value = '',
    options,
    inline = false,
    disabled = false,
    ariaLabel,
    onchange,
  }: {
    value?: string | number;
    options: SelectOption[];
    inline?: boolean;
    disabled?: boolean;
    ariaLabel?: string;
    onchange?: (value: string) => void;
  } = $props();

  const optionValue = (option: SelectOption) => typeof option === 'string' ? option : option.value;
  const optionLabel = (option: SelectOption) => typeof option === 'string' ? option : option.label;
</script>

<select class:v2-select-inline={inline} value={String(value)} {disabled} aria-label={ariaLabel} onchange={(event) => onchange?.(event.currentTarget.value)}>
  {#each options as option}<option value={optionValue(option)}>{optionLabel(option)}</option>{/each}
</select>
