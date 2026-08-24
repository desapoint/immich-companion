<script lang="ts">
  import { aspectRatioValidationMessage } from '../../utils/aspectRatio';

  interface Props {
    id: string;
    label: string;
    value: string;
    disabled?: boolean;
    required?: boolean;
    compact?: boolean;
    onchange: (value: string) => void;
  }

  let {
    id,
    label,
    value,
    disabled = false,
    required = false,
    compact = false,
    onchange,
  }: Props = $props();
  let inputElement: HTMLInputElement;

  function validate(input: HTMLInputElement, nextValue: string): void {
    input.setCustomValidity(aspectRatioValidationMessage(nextValue));
  }

  function update(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    validate(input, input.value);
    onchange(input.value);
  }

  $effect(() => {
    value;
    if (inputElement) validate(inputElement, value);
  });
</script>

<label class:compact>
  <span>{label}</span>
  <input
    bind:this={inputElement}
    {id}
    type="text"
    inputmode="decimal"
    autocomplete="off"
    placeholder="16/9 or 1.7778"
    aria-describedby={`${id}-hint`}
    {value}
    {disabled}
    {required}
    oninput={update}
  />
  <small id={`${id}-hint`}>Positive decimals and fractions are accepted.</small>
</label>

<style>
  label {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  label > span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  input {
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
  }

  .compact input {
    min-height: 2.3rem;
    padding: 0.42rem 0.68rem;
    font-size: 0.78rem;
  }

  input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  input:invalid:not(:placeholder-shown) {
    border-color: var(--color-negative-ink);
  }

  input:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  small {
    color: var(--color-ink-muted);
    font-size: 0.58rem;
  }
</style>
