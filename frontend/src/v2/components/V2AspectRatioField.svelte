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
  .v2-aspect-ratio-field { display:grid; min-width:0; gap:.35rem; }
  .v2-aspect-ratio-input-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:.45rem; align-items:center; }
  input { width:100%; min-width:0; min-height:2.55rem; padding:.56rem .68rem; border:1px solid var(--v2-border-strong); border-radius:var(--v2-radius-sm); color:var(--v2-text); background:var(--v2-surface); font:inherit; }
  input:focus-visible { outline:.16rem solid color-mix(in srgb, var(--v2-accent-2) 35%, transparent); outline-offset:.08rem; }
  input[aria-invalid='true'] { border-color:var(--v2-danger, #e05a5a); }
  input:disabled { cursor:not-allowed; opacity:.58; }
  .v2-aspect-ratio-hint { min-height:1rem; color:var(--v2-muted); font-size:.72rem; }
  .v2-aspect-ratio-hint.invalid { color:var(--v2-danger, #e05a5a); }
</style>
