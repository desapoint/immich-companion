<script lang="ts">
  let {
    label,
    value = '',
    type = 'text',
    placeholder = '',
    multiline = false,
    disabled = false,
    min,
    max,
    step,
    onchange,
  }: {
    label: string;
    value?: string | number;
    type?: string;
    placeholder?: string;
    multiline?: boolean;
    disabled?: boolean;
    min?: string | number;
    max?: string | number;
    step?: string | number;
    onchange?: (value: string) => void;
  } = $props();
</script>

<label class="v2-field">
  <span class="v2-field-label">{label}</span>
  {#if multiline}
    <textarea value={String(value)} {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}></textarea>
  {:else}
    <input {type} value={value} {placeholder} {disabled} {min} {max} {step} onchange={(event) => onchange?.(event.currentTarget.value)}>
  {/if}
</label>
