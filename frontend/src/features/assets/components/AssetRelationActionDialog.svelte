<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import ColorPicker from '../../relations/components/ColorPicker.svelte';
  import { createAlbum, createTag } from '../api/assetApi';
  import type { IconName, SelectOption } from '../../../lib/types/ui';
  import {
    ALL_RELATIONS_VALUE,
    relationDialogOptions,
    resolveRelationSelection,
    updateRelationSelection,
  } from '../state/relationAction';
  import type { AssetActionIntent } from '../types/assets';

  type RelationAction = Extract<
    AssetActionIntent,
    'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'
  >;

  interface Props {
    action: RelationAction;
    options: SelectOption[];
    selectedCount: number;
    targetLabel: string;
    busy?: boolean;
    onapply: (relationIds: string[]) => void;
    onclose: () => void;
  }

  let {
    action,
    options,
    selectedCount,
    targetLabel,
    busy = false,
    onapply,
    onclose,
  }: Props = $props();
  let values = $state<string[]>([]);
  let createOpen = $state(false);
  let createName = $state('');
  let createDescription = $state('');
  let createColor = $state('#6b7cff');
  let createBusy = $state(false);
  let createError = $state<string | null>(null);

  const isAlbum = $derived(action.endsWith('album'));
  const isRemove = $derived(action.startsWith('remove'));
  const relationName = $derived(isAlbum ? 'albums' : 'tags');
  const title = $derived.by(() => {
    if (action === 'add_album') return 'Add to albums';
    if (action === 'remove_album') return 'Remove from albums';
    if (action === 'add_tag') return 'Add tags';
    return 'Remove tags';
  });
  const description = $derived(
    `${selectedCount} ${targetLabel} · choose one or more ${relationName}`,
  );
  const dialogOptions = $derived<SelectOption[]>(
    relationDialogOptions(options, isRemove, relationName),
  );
  const resolvedValues = $derived(resolveRelationSelection(values, options));
  const confirmLabel = $derived(
    values.includes(ALL_RELATIONS_VALUE)
      ? isAlbum ? 'Remove from all albums' : 'Remove all tags'
      : title,
  );
  const icon = $derived<IconName>(action === 'add_album'
    ? 'album-add'
    : action === 'remove_album'
      ? 'album-remove'
      : action === 'add_tag'
        ? 'tag-add'
        : 'tag-remove');

  function updateValues(next: string[]): void {
    values = updateRelationSelection(values, next, isRemove);
  }

  function beginCreate(value: string): void {
    createName = value;
    createDescription = '';
    createColor = '#6b7cff';
    createError = null;
    createOpen = true;
  }

  async function saveCreatedRelation(): Promise<void> {
    if (!createName.trim()) return;
    createBusy = true;
    createError = null;
    try {
      const relation = isAlbum
        ? await createAlbum(createName.trim(), createDescription)
        : await createTag(createName.trim(), createColor);
      createOpen = false;
      onapply([relation.id]);
    } catch (cause) {
      createError = cause instanceof Error ? cause.message : 'The relation could not be created.';
    } finally {
      createBusy = false;
    }
  }
</script>

<ConfirmDialog
  {title}
  message={description}
  {confirmLabel}
  {icon}
  {busy}
  confirmDisabled={resolvedValues.length === 0}
  onconfirm={() => onapply(resolvedValues)}
  {onclose}
>
  <MultiSelectField
    id={`asset-action-${action}`}
    label={isAlbum ? 'Albums' : 'Tags'}
    {values}
    options={dialogOptions}
    placeholder={`Choose ${relationName}`}
    disabled={busy}
    required
    searchable
    allowCreate={!isRemove}
    createLabel={isAlbum ? 'Add album' : 'Add tag'}
    oncreate={beginCreate}
    onchange={updateValues}
  />
</ConfirmDialog>

{#if createOpen}
  <ConfirmDialog
    title={`Create ${isAlbum ? 'album' : 'tag'}`}
    message={`Create this ${isAlbum ? 'album' : 'tag'} and apply it to the selected ${targetLabel}.`}
    confirmLabel="Create and apply"
    icon={isAlbum ? 'album-add' : 'tag-add'}
    busy={createBusy}
    confirmDisabled={!createName.trim()}
    onconfirm={saveCreatedRelation}
    onclose={() => { if (!createBusy) createOpen = false; }}
  >
    {#snippet children()}
      <div class="create-form">
        <label>Name<input bind:value={createName} autocomplete="off" data-1p-ignore data-bwignore="true" maxlength="255" /></label>
        {#if isAlbum}
          <label>Description<textarea bind:value={createDescription} maxlength="2000"></textarea></label>
        {:else}
          <label>Color<ColorPicker value={createColor} onchange={(next) => (createColor = next)} /></label>
        {/if}
        {#if createError}<p class="create-error" role="alert">{createError}</p>{/if}
      </div>
    {/snippet}
  </ConfirmDialog>
{/if}

<style>
  .create-form { display: grid; gap: .8rem; }
  label { display: grid; gap: .3rem; color: var(--color-ink-muted); font-size: .76rem; font-weight: 760; }
  input, textarea { width: 100%; box-sizing: border-box; padding: .58rem .65rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: inherit; }
  textarea { min-height: 4.5rem; resize: vertical; }
  .create-error { margin: 0; color: #a33d45; font-size: .74rem; }
</style>
