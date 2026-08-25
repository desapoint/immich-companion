<script lang="ts">
  import Dialog from '../../../lib/components/ui/Dialog.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import type { AssetActionIntent } from '../types/assets';

  type RelationAction = Extract<
    AssetActionIntent,
    'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'
  >;

  interface Props {
    action: RelationAction;
    options: SelectOption[];
    selectedCount: number;
    busy?: boolean;
    onapply: (relationIds: string[]) => void;
    onclose: () => void;
  }

  let {
    action,
    options,
    selectedCount,
    busy = false,
    onapply,
    onclose,
  }: Props = $props();
  let values = $state<string[]>([]);

  const isAlbum = $derived(action.endsWith('album'));
  const isAdd = $derived(action.startsWith('add'));
  const relationName = $derived(isAlbum ? 'albums' : 'tags');
  const title = $derived(`${isAdd ? 'Add' : 'Remove'} ${relationName}`);
  const description = $derived(
    `${selectedCount} selected asset${selectedCount === 1 ? '' : 's'} · choose one or more ${relationName}`,
  );
</script>

<Dialog {title} {description} size="small" {onclose}>
  <MultiSelectField
    id={`asset-action-${action}`}
    label={isAlbum ? 'Albums' : 'Tags'}
    {values}
    {options}
    placeholder={`Choose ${relationName}`}
    disabled={busy}
    required
    searchable
    onchange={(next) => (values = next)}
  />
  {#snippet footer()}
    <div class="dialog-actions">
      <button type="button" onclick={onclose} disabled={busy}>Cancel</button>
      <button
        class="continue"
        type="button"
        onclick={() => onapply(values)}
        disabled={busy || values.length === 0}
      >Review {title.toLocaleLowerCase()}</button>
    </div>
  {/snippet}
</Dialog>

<style>
  .dialog-actions {
    display: flex;
    width: 100%;
    justify-content: flex-end;
    gap: 0.55rem;
  }

  button {
    min-height: 2.4rem;
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 780;
  }

  button.continue { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  button:disabled { cursor: default; opacity: 0.5; }
</style>
