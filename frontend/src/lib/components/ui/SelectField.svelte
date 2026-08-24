<script lang="ts">
  export interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
  }

  interface Props {
    id: string;
    label: string;
    value: string;
    options: SelectOption[];
    disabled?: boolean;
    required?: boolean;
    compact?: boolean;
    onchange: (value: string) => void;
  }

  let {
    id,
    label,
    value,
    options,
    disabled = false,
    required = false,
    compact = false,
    onchange,
  }: Props = $props();
</script>

<label class:compact>
  <span>{label}</span>
  <select
    {id}
    {value}
    {disabled}
    {required}
    onchange={(event) => onchange(event.currentTarget.value)}
  >
    {#each options as option (option.value)}
      <option value={option.value} disabled={option.disabled}>{option.label}</option>
    {/each}
  </select>
</label>

<style>
  label {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  select {
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    padding: 0.56rem 2rem 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
  }

  .compact select {
    min-height: 2.3rem;
    padding-block: 0.42rem;
    font-size: 0.78rem;
  }

  select:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  select:disabled {
    cursor: wait;
    opacity: 0.58;
  }
</style>
