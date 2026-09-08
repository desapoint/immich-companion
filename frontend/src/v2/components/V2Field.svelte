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
    onenter,
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
    onenter?: (value: string) => void;
  } = $props();

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' || event.isComposing || multiline || !onenter) return;
    event.preventDefault();
    onenter(event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value : String(value));
  }
</script>

<label class="v2-field">
  <span class="v2-field-label">{label}</span>
  {#if multiline}
    <textarea value={String(value)} {placeholder} {disabled} onchange={(event) => onchange?.(event.currentTarget.value)}></textarea>
  {:else}
    <input {type} value={value} {placeholder} {disabled} {min} {max} {step} onchange={(event) => onchange?.(event.currentTarget.value)} onkeydown={handleKeydown}>
  {/if}
</label>
