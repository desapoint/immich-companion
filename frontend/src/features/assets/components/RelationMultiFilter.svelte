<script lang="ts">
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';

  interface Props {
    id: string;
    label: string;
    values: string[];
    options: SelectOption[];
    placeholder: string;
    emptySelected: boolean;
    emptyLabel: string;
    disabled?: boolean;
    onvalueschange: (values: string[]) => void;
    onemptychange: (selected: boolean) => void;
  }

  let {
    id,
    label,
    values,
    options,
    placeholder,
    emptySelected,
    emptyLabel,
    disabled = false,
    onvalueschange,
    onemptychange,
  }: Props = $props();
</script>

<div class="relation-filter">
  <MultiSelectField
    {id}
    {label}
    {values}
    {options}
    {placeholder}
    {disabled}
    searchable
    onchange={onvalueschange}
  />
  <button
    type="button"
    class:active={emptySelected}
    aria-pressed={emptySelected}
    {disabled}
    onclick={() => onemptychange(!emptySelected)}
  >{emptyLabel}</button>
</div>

<style>
  .relation-filter {
    display: grid;
    min-width: 0;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 0.45rem;
  }

  button {
    min-height: 2.55rem;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    cursor: pointer;
    font: inherit;
    font-size: 0.7rem;
    font-weight: 760;
    white-space: nowrap;
  }

  button:hover:not(:disabled),
  button.active {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 10%, var(--color-surface-soft));
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  @media (max-width: 34rem) {
    .relation-filter {
      grid-template-columns: 1fr;
    }

    button {
      justify-self: start;
    }
  }
</style>
