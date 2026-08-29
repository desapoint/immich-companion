<script lang="ts">
  import AspectRatioField from '../../../lib/components/ui/AspectRatioField.svelte';
  import DateTimePicker from '../../../lib/components/ui/DateTimePicker.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import { resetSearchConditionField } from '../state/assetViewModel';
  import type {
    AlbumOption,
    SearchCondition,
    SearchField,
    SearchOperator,
    TagOption,
  } from '../types/assets';

  interface Props {
    condition: SearchCondition;
    albums: AlbumOption[];
    tags: TagOption[];
    disabled?: boolean;
    onremove: () => void;
  }

  let { condition, albums, tags, disabled = false, onremove }: Props = $props();

  const fieldOptions: SelectOption[] = [
    { value: 'filename', label: 'Filename' },
    { value: 'type', label: 'Media type' },
    { value: 'taken_at', label: 'Taken date' },
    { value: 'width', label: 'Width' },
    { value: 'height', label: 'Height' },
    { value: 'aspect_ratio', label: 'Aspect ratio' },
    { value: 'favorite', label: 'Favorite' },
    { value: 'archived', label: 'Archived' },
    { value: 'album', label: 'Album' },
    { value: 'tag', label: 'Tag' },
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
    if (condition.field === 'album' || condition.field === 'tag') return [
      { value: 'in_any', label: 'matches any selected (OR)' },
      { value: 'in_all', label: 'matches all selected (AND)' },
      { value: 'not_in_any', label: 'matches none selected (NOT)' },
      { value: 'has_none', label: `has no ${condition.field === 'album' ? 'albums' : 'tags'}` },
    ];
    if (condition.field === 'aspect_ratio') return [
      { value: 'at_least', label: 'is at least' },
      { value: 'at_most', label: 'is at most' },
      { value: 'equals', label: 'is approximately' },
    ];
    if (condition.field === 'width' || condition.field === 'height') return [
      { value: 'at_least', label: 'is at least' },
      { value: 'at_most', label: 'is at most' },
      { value: 'equals', label: 'is equal to' },
    ];
    return [{ value: 'equals', label: 'is' }];
  });

  const albumOptions = $derived<SelectOption[]>(albums.map((album) => ({
      value: album.id,
      label: `${album.name} (${album.asset_count})`,
    })));
  const tagOptions = $derived<SelectOption[]>(tags.map((tag) => ({
    value: tag.id,
    label: `${tag.name} (${tag.asset_count})`,
  })));
  const scalarValue = $derived(Array.isArray(condition.value) ? '' : condition.value);
  const relationValues = $derived(Array.isArray(condition.value) ? condition.value : []);

  function changeField(value: string): void {
    resetSearchConditionField(condition, value as SearchField);
  }

  function changeOperator(value: string): void {
    condition.operator = value as SearchOperator;
    if ((condition.field === 'album' || condition.field === 'tag') && value === 'has_none') {
      condition.value = [];
    }
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
    onchange={changeOperator}
  />

  {#if condition.field === 'type'}
    <SelectField
      id={`${condition.id}-value`}
      label="Value"
      value={scalarValue}
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
  {:else if condition.field === 'favorite' || condition.field === 'archived'}
    <SelectField
      id={`${condition.id}-value`}
      label="Value"
      value={scalarValue}
      options={[{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }]}
      {disabled}
      required
      compact
      onchange={(value) => (condition.value = value)}
    />
  {:else if condition.field === 'album' || condition.field === 'tag'}
    {#if condition.operator === 'has_none'}
      <div class="empty-relation-value">
        <span>Value</span>
        <strong>No {condition.field === 'album' ? 'album' : 'tag'} membership</strong>
      </div>
    {:else}
      <MultiSelectField
        id={`${condition.id}-value`}
        label={condition.field === 'album' ? 'Albums' : 'Tags'}
        values={relationValues}
        options={condition.field === 'album' ? albumOptions : tagOptions}
        placeholder={condition.field === 'album' ? 'Choose albums' : 'Choose tags'}
        {disabled}
        required
        compact
        searchable
        onchange={(values) => (condition.value = values)}
      />
    {/if}
  {:else if condition.field === 'taken_at'}
    <DateTimePicker
      id={`${condition.id}-value`}
      label="Date and time"
      value={scalarValue}
      {disabled}
      required
      onchange={(value) => (condition.value = value)}
    />
  {:else if condition.field === 'aspect_ratio'}
    <AspectRatioField
      id={`${condition.id}-value`}
      label="Value"
      value={scalarValue}
      {disabled}
      required
      compact
      onchange={(value) => (condition.value = value)}
    />
  {:else}
    <label class="value-field">
      <span>Value</span>
      <input
        id={`${condition.id}-value`}
        type={condition.field === 'filename' ? 'text' : 'number'}
        min={condition.field === 'filename' ? undefined : '0.01'}
        step={condition.field === 'filename' ? undefined : '1'}
        placeholder={condition.field === 'filename' ? 'IMG_2026' : '1920'}
        value={scalarValue}
        oninput={(event) => (condition.value = event.currentTarget.value)}
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
    align-items: start;
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

  .empty-relation-value {
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .empty-relation-value span {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  .empty-relation-value strong {
    display: flex;
    min-height: 2.3rem;
    align-items: center;
    padding: 0.42rem 0.68rem;
    border: 1px dashed var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    font-size: 0.76rem;
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

  .remove {
    align-self: start;
    margin-top: 1.42rem;
  }

  @media (max-width: 52rem) {
    .condition-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .remove {
      justify-self: end;
      margin-top: 0;
    }
  }

  @media (max-width: 34rem) {
    .condition-row {
      grid-template-columns: 1fr;
    }
  }
</style>
