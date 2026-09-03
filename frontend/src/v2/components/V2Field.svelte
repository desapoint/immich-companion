<script lang="ts">
  let {
    label,
    value = '',
    type = 'text',
    placeholder = '',
    multiline = false,
    disabled = false,
    onchange,
  }: {
    label: string;
    value?: string | number;
    type?: string;
    placeholder?: string;
    multiline?: boolean;
    disabled?: boolean;
    onchange?: (value: string) => void;
  } = $props();
</script>

<label class="v2-field">
  <span class="v2-field-label">{label}</span>
  {#if multiline}
    <textarea value={String(value)} {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}></textarea>
  {:else}
    <input {type} value={value} {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}>
  {/if}
</label>
