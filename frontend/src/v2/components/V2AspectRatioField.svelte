<script lang="ts">
  import V2Button from './V2Button.svelte';
  import { formatAspectDecimal, invertAspectRatio, parseAspectRatio } from '../state/aspectRatio';

  let {
    id,
    label,
    value = '',
    placeholder = '16:9, 16/9, 16-9 or 1.778',
    disabled = false,
    onchange,
  }: {
    id: string;
    label: string;
    value?: string;
    placeholder?: string;
    disabled?: boolean;
    onchange: (value: string) => void;
  } = $props();

  const parsed = $derived(parseAspectRatio(value));
  const counterpart = $derived(parsed
    ? parsed.source === 'ratio'
      ? `${parsed.ratio} = ${formatAspectDecimal(parsed.decimal)}`
      : `${formatAspectDecimal(parsed.decimal)} ≈ ${parsed.ratio}`
    : '');

  function invert(): void {
    const next = invertAspectRatio(value);
    if (next) onchange(next);
  }
</script>

<div class="v2-aspect-ratio-field">
  <label for={id} class="v2-field-label">{label}</label>
  <div class="v2-aspect-ratio-input-row">
    <input
      {id}
      type="text"
      inputmode="decimal"
      value={value}
      {placeholder}
      {disabled}
      aria-invalid={value.trim() && !parsed ? 'true' : undefined}
      aria-describedby={`${id}-hint`}
      oninput={(event) => onchange(event.currentTarget.value)}
    >
    <V2Button disabled={disabled || !parsed} onclick={invert}>Invert</V2Button>
  </div>
  <div id={`${id}-hint`} class:invalid={value.trim() && !parsed} class="v2-aspect-ratio-hint">
    {#if value.trim() && !parsed}
      Enter a positive ratio such as 16:9, 16/9, 16-9, or a decimal such as 1.778.
    {:else if parsed}
      {counterpart}
    {:else}
      Ratio or decimal accepted.
    {/if}
  </div>
</div>

<style>
  .v2-aspect-ratio-field { display:grid; min-width:0; gap:5px; }
  .v2-aspect-ratio-input-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; align-items:center; }
  input { width:100%; min-width:0; min-height:36px; font:inherit; }
  input[aria-invalid='true'] { border-color:#713d43; }
  input:disabled { cursor:default; opacity:.5; }
  .v2-aspect-ratio-hint { min-height:1rem; color:var(--v2-muted); font-size:11px; line-height:1.35; }
  .v2-aspect-ratio-hint.invalid { color:#ffb1b1; }
</style>
