<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
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
    onchange={updateValues}
  />
</ConfirmDialog>
