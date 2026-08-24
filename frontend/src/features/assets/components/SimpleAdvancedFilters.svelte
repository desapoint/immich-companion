<script lang="ts">
  import DateTimePicker from '../../../lib/components/ui/DateTimePicker.svelte';
  import type { SimpleAssetSearchFilters } from '../types/assets';

  type NumericFilter =
    | 'minWidth'
    | 'maxWidth'
    | 'minHeight'
    | 'maxHeight'
    | 'minAspectRatio'
    | 'maxAspectRatio';

  interface Props {
    filters: SimpleAssetSearchFilters;
    disabled?: boolean;
    onchange: (filters: SimpleAssetSearchFilters) => void;
  }

  let { filters, disabled = false, onchange }: Props = $props();
  let open = $state(false);
  const componentId = $props.id();
  const activeCount = $derived([
    filters.takenAfter,
    filters.takenBefore,
    filters.minWidth,
    filters.maxWidth,
    filters.minHeight,
    filters.maxHeight,
    filters.minAspectRatio,
    filters.maxAspectRatio,
  ].filter((value) => value.trim()).length);
</script>

{#snippet numberField(
  field: NumericFilter,
  label: string,
  placeholder: string,
  step: string,
  minimum: string,
)}
  <label>
    <span>{label}</span>
    <input
      id={`${componentId}-${field}`}
      type="number"
      value={filters[field]}
      min={minimum}
      {step}
      {placeholder}
      {disabled}
      oninput={(event) => onchange({ ...filters, [field]: event.currentTarget.value })}
    />
  </label>
{/snippet}

<details bind:open>
  <summary>
    <span class="summary-title">Advanced</span>
    <small>{activeCount > 0 ? `${activeCount} active filters` : 'Dates, dimensions, and aspect ratio'}</small>
    <strong aria-hidden="true">{open ? '−' : '+'}</strong>
  </summary>

  <div class="advanced-fields">
    <DateTimePicker
      id={`${componentId}-taken-after`}
      label="Taken after"
      value={filters.takenAfter}
      {disabled}
      onchange={(value) => onchange({ ...filters, takenAfter: value })}
    />
    <DateTimePicker
      id={`${componentId}-taken-before`}
      label="Taken before"
      value={filters.takenBefore}
      {disabled}
      onchange={(value) => onchange({ ...filters, takenBefore: value })}
    />
    {@render numberField('minWidth', 'Minimum width', '1280', '1', '1')}
    {@render numberField('maxWidth', 'Maximum width', '4096', '1', '1')}
    {@render numberField('minHeight', 'Minimum height', '720', '1', '1')}
    {@render numberField('maxHeight', 'Maximum height', '2160', '1', '1')}
    {@render numberField('minAspectRatio', 'Minimum aspect ratio', '1.33', '0.01', '0.01')}
    {@render numberField('maxAspectRatio', 'Maximum aspect ratio', '1.78', '0.01', '0.01')}
  </div>
</details>

<style>
  details {
    overflow: visible;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    background: var(--color-surface-soft);
  }

  summary {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.65rem;
    min-height: 2.75rem;
    padding: 0.58rem 0.72rem;
    color: var(--color-ink-strong);
    cursor: pointer;
    list-style: none;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary:hover {
    background: color-mix(in srgb, var(--color-accent-strong) 6%, transparent);
  }

  summary:focus-visible {
    outline: 0.18rem solid var(--color-accent-strong);
    outline-offset: -0.18rem;
  }

  .summary-title {
    color: var(--color-accent-strong);
    font-size: 0.74rem;
    font-weight: 800;
  }

  small {
    overflow: hidden;
    color: var(--color-ink-muted);
    font-size: 0.7rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    display: grid;
    width: 1.65rem;
    height: 1.65rem;
    place-items: center;
    border: 1px solid var(--color-border-strong);
    border-radius: 50%;
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    font-size: 1rem;
  }

  .advanced-fields {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.65rem;
    padding: 0.75rem;
    border-top: 1px solid var(--color-border-subtle);
    background: var(--color-surface-raised);
  }

  label {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  label span {
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

  input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  input:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  @media (max-width: 68rem) {
    .advanced-fields {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 34rem) {
    .advanced-fields {
      grid-template-columns: 1fr;
    }

    small {
      white-space: normal;
    }
  }
</style>
