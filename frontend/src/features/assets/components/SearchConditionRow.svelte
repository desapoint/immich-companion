<script lang="ts">
  import DateTimePicker from '../../../lib/components/ui/DateTimePicker.svelte';
  import SelectField, { type SelectOption } from '../../../lib/components/ui/SelectField.svelte';
  import { resetSearchConditionField } from '../state/assetViewModel';
  import type {
    AlbumOption,
    SearchCondition,
    SearchField,
    SearchOperator,
  } from '../types/assets';

  interface Props {
    condition: SearchCondition;
    albums: AlbumOption[];
    disabled?: boolean;
    onremove: () => void;
  }

  let { condition, albums, disabled = false, onremove }: Props = $props();

  const fieldOptions: SelectOption[] = [
    { value: 'filename', label: 'Filename' },
    { value: 'type', label: 'Media type' },
    { value: 'taken_at', label: 'Taken date' },
    { value: 'width', label: 'Width' },
    { value: 'height', label: 'Height' },
    { value: 'aspect_ratio', label: 'Aspect ratio' },
    { value: 'favorite', label: 'Favorite' },
    { value: 'archived', label: 'Archived' },
    { value: 'trashed', label: 'Trashed' },
    { value: 'album', label: 'Album' },
  ];

  const operatorOptions = $derived.by<SelectOption[]>(() => {
    if (condition.field === 'filename') return [
      { value: 'contains', label: 'contains' },
      { value: 'equals', label: 'is exactly' },
      { value: 'not_equals', label: 'is not' },
    ];
    if (condition.field === 'type') return [
      { value: 'equals', label: 'is' },
      { value: 'not_equals', label: 'is not' },
    ];
    if (condition.field === 'taken_at') return [
      { value: 'after', label: 'is on or after' },
      { value: 'before', label: 'is on or before' },
    ];
    if (condition.field === 'album') return [
      { value: 'in_album', label: 'is in' },
      { value: 'not_in_album', label: 'is not in' },
    ];
    if (condition.field === 'width' || condition.field === 'height' || condition.field === 'aspect_ratio') return [
      { value: 'at_least', label: 'is at least' },
      { value: 'at_most', label: 'is at most' },
      { value: 'equals', label: 'is equal to' },
    ];
    return [{ value: 'equals', label: 'is' }];
  });

  const albumOptions = $derived<SelectOption[]>([
    { value: '', label: albums.length ? 'Choose an album' : 'No synchronized albums', disabled: true },
    ...albums.map((album) => ({
      value: album.id,
      label: `${album.name} (${album.asset_count})`,
    })),
  ]);

  function changeField(value: string): void {
    resetSearchConditionField(condition, value as SearchField);
  }
</script>

<div class="condition-row">
  <SelectField
    id={`${condition.id}-field`}
    label="Field"
    value={condition.field}
    options={fieldOptions}
    {disabled}
    compact
    onchange={changeField}
  />
  <SelectField
    id={`${condition.id}-operator`}
    label="Match"
    value={condition.operator}
    options={operatorOptions}
    {disabled}
    compact
    onchange={(value) => (condition.operator = value as SearchOperator)}
  />

  {#if condition.field === 'type'}
    <SelectField
      id={`${condition.id}-value`}
      label="Value"
      value={condition.value}
      options={[
        { value: 'IMAGE', label: 'Image' },
        { value: 'VIDEO', label: 'Video' },
        { value: 'AUDIO', label: 'Audio' },
        { value: 'OTHER', label: 'Other' },
      ]}
      {disabled}
      required
      compact
      onchange={(value) => (condition.value = value)}
    />
  {:else if condition.field === 'favorite' || condition.field === 'archived' || condition.field === 'trashed'}
    <SelectField
      id={`${condition.id}-value`}
      label="Value"
      value={condition.value}
      options={[{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }]}
      {disabled}
      required
      compact
      onchange={(value) => (condition.value = value)}
    />
  {:else if condition.field === 'album'}
    <SelectField
      id={`${condition.id}-value`}
      label="Album"
      value={condition.value}
      options={albumOptions}
      {disabled}
      required
      compact
      onchange={(value) => (condition.value = value)}
    />
  {:else if condition.field === 'taken_at'}
    <DateTimePicker
      id={`${condition.id}-value`}
      label="Date and time"
      value={condition.value}
      {disabled}
      required
      onchange={(value) => (condition.value = value)}
    />
  {:else}
    <label class="value-field">
      <span>Value</span>
      <input
        id={`${condition.id}-value`}
        type={condition.field === 'filename' ? 'text' : 'number'}
        min={condition.field === 'filename' ? undefined : '0.01'}
        step={condition.field === 'aspect_ratio' ? '0.01' : condition.field === 'filename' ? undefined : '1'}
        placeholder={condition.field === 'aspect_ratio' ? '1.78' : condition.field === 'filename' ? 'IMG_2026' : '1920'}
        bind:value={condition.value}
        {disabled}
        required
      />
    </label>
  {/if}

  <button class="remove" type="button" onclick={onremove} {disabled} aria-label="Remove condition" title="Remove condition">×</button>
</div>

<style>
  .condition-row {
    display: grid;
    grid-template-columns: minmax(8rem, 0.8fr) minmax(9rem, 0.9fr) minmax(10rem, 1.5fr) auto;
    align-items: end;
    gap: 0.55rem;
    padding: 0.65rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
  }

  .value-field {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .value-field span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  input {
    width: 100%;
    min-width: 0;
    min-height: 2.3rem;
    padding: 0.42rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
    font-size: 0.78rem;
  }

  button {
    min-width: 2.3rem;
    min-height: 2.3rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-negative-ink);
    background: var(--color-surface-soft);
    cursor: pointer;
    font: inherit;
    font-size: 1.1rem;
  }

  @media (max-width: 52rem) {
    .condition-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .remove {
      justify-self: end;
    }
  }

  @media (max-width: 34rem) {
    .condition-row {
      grid-template-columns: 1fr;
    }
  }
</style>
