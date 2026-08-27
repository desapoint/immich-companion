<script lang="ts">
  import ActionMenu from '../../../lib/components/ui/ActionMenu.svelte';
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import type { ActionMenuItem, SelectOption } from '../../../lib/types/ui';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetSelectionSummary,
    TagOption,
  } from '../types/assets';
  import AssetRelationActionDialog from './AssetRelationActionDialog.svelte';

  type RelationAction = Extract<
    AssetActionIntent,
    'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'
  >;

  interface Props {
    summary: AssetSelectionSummary | null;
    albums: AlbumOption[];
    tags: TagOption[];
    targetCount: number;
    targetLabel: string;
    allowStackRemoval?: boolean;
    isStackPrimary?: boolean;
    onsetprimary?: () => void;
    allowStack?: boolean;
    busy?: boolean;
    onplan: (action: AssetActionIntent, relationIds?: string[]) => void;
    onrelationconfirm: (action: RelationAction, relationIds: string[]) => void;
  }

  let {
    summary,
    albums,
    tags,
    targetCount,
    targetLabel,
    allowStackRemoval = false,
    isStackPrimary = false,
    onsetprimary,
    allowStack = true,
    busy = false,
    onplan,
    onrelationconfirm,
  }: Props = $props();
  let relationAction = $state<RelationAction | null>(null);

  const albumOptions = $derived<SelectOption[]>(albums.map((album) => ({
    value: album.id,
    label: `${album.name} (${album.asset_count})`,
  })));
  const tagOptions = $derived<SelectOption[]>(tags.map((tag) => ({
    value: tag.id,
    label: `${tag.name} (${tag.asset_count})`,
  })));
  const relationOptions = $derived(
    relationAction?.endsWith('album') ? albumOptions : tagOptions,
  );
  const primaryTrashAction = $derived(
    summary?.can_trash ? 'trash' : summary?.can_restore ? 'restore' : null,
  );
  const overflowItems = $derived.by(() => {
    const items: ActionMenuItem[] = [];
    if (summary?.archive_action) {
      items.push({
        id: 'archive_toggle',
        icon: summary.archive_action,
        label: `${summary.archive_action === 'archive' ? 'Archive' : 'Unarchive'} ${targetLabel}`,
      });
    }
    if (allowStack) items.push({
      id: 'stack',
      icon: 'stack',
      label: `Stack ${targetLabel}`,
    });
    if (allowStackRemoval) {
      if (!isStackPrimary) {
        items.push({
          id: 'set_stack_primary',
          icon: 'star',
          label: 'Set as primary',
        });
      }
      items.push(
        {
          id: 'remove_from_stack',
          icon: 'stack',
          label: `Remove ${targetLabel} from stack`,
        },
        {
          id: 'remove_stack',
          icon: 'stack',
          label: 'Remove complete stack',
        },
      );
    }
    items.push(
      {
        id: 'add_tag',
        icon: 'tag-add',
        label: `Add tags to ${targetLabel}`,
      },
      {
        id: 'remove_tag',
        icon: 'tag-remove',
        label: `Remove tags from ${targetLabel}`,
        disabled: tags.length === 0,
      },
      {
        id: 'remove_album',
        icon: 'album-remove',
        label: `Remove ${targetLabel} from albums`,
        disabled: albums.length === 0,
      },
    );
    if (summary?.can_trash && summary.can_restore) {
      items.push({
        id: 'restore',
        icon: 'restore',
        label: `Restore applicable ${targetLabel}`,
      });
    }
    return items;
  });

  function titleCase(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function handleMenuAction(action: string): void {
    if (['add_tag', 'remove_tag', 'remove_album'].includes(action)) {
      relationAction = action as RelationAction;
      return;
    }
    if (action === 'set_stack_primary') {
      onsetprimary?.();
      return;
    }
    onplan(action as AssetActionIntent);
  }

  function applyRelation(relationIds: string[]): void {
    if (!relationAction || relationIds.length === 0) return;
    onrelationconfirm(relationAction, relationIds);
    relationAction = null;
  }
</script>

<div class="asset-action-controls" aria-label={`Actions for ${targetLabel}`}>
  <IconButton
    icon="album-add"
    label={`Add ${targetLabel} to album`}
    disabled={busy}
    onclick={() => (relationAction = 'add_album')}
  />
  {#if summary?.favorite_action}
    <IconButton
      icon={summary.favorite_action}
      label={`${titleCase(summary.favorite_action)} ${targetLabel}`}
      disabled={busy}
      tone="accent"
      onclick={() => onplan('favorite_toggle')}
    />
  {/if}
  {#if primaryTrashAction}
    <IconButton
      icon={primaryTrashAction}
      label={primaryTrashAction === 'trash'
        ? `Delete ${targetLabel} (move to trash)`
        : `Restore ${targetLabel} from trash`}
      disabled={busy}
      tone={primaryTrashAction === 'trash' ? 'destructive' : 'default'}
      onclick={() => onplan(primaryTrashAction)}
    />
  {/if}
  <ActionMenu
    items={overflowItems}
    label={`More actions for ${targetLabel}`}
    disabled={busy}
    onselect={handleMenuAction}
  />
</div>

{#if relationAction}
  <AssetRelationActionDialog
    action={relationAction}
    options={relationOptions}
    selectedCount={targetCount}
    {targetLabel}
    {busy}
    onapply={applyRelation}
    onclose={() => (relationAction = null)}
  />
{/if}

<style>
  .asset-action-controls {
    display: flex;
    align-items: center;
    gap: 0.38rem;
  }
</style>
