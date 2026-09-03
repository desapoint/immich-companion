<script lang="ts">
  let {
    label,
    value = '',
    type = 'text',
    options = [],
    placeholder = '',
    multiline = false,
    disabled = false,
    onchange,
  }: {
    label: string;
    value?: string | number;
    type?: string;
    options?: string[];
    placeholder?: string;
    multiline?: boolean;
    disabled?: boolean;
    onchange?: (value: string) => void;
  } = $props();
</script>

<label class="v2-field">
  <span>{label}</span>
  {#if options.length}
    <select value={String(value)} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}>
      {#each options as option}<option>{option}</option>{/each}
    </select>
  {:else if multiline}
    <textarea {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}>{value}</textarea>
  {:else}
    <input {type} value={value} {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}>
  {/if}
</label>
