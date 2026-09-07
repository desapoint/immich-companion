<script lang="ts">
  import { Pencil, Play, RefreshCw, Save, Trash2 } from '@lucide/svelte';
  import ConfirmDialog from './V2ConfirmDialog.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ErrorState from './V2ErrorState.svelte';
  import V2Field from './V2Field.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2OperationFeedback from './V2OperationFeedback.svelte';
  import V2SavedSearchModal from './V2SavedSearchModal.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2Toolbar from './V2Toolbar.svelte';
  import type { AssetSearchCriteria, SavedSearchRecord } from '../data/contracts';
  import type { SavedSearchController } from '../state/savedSearches.svelte';

  type Confirmation = {
    action: 'replace' | 'delete';
    record: SavedSearchRecord;
  };

  let { controller, currentCriteria, onopen }: { controller: SavedSearchController; currentCriteria: AssetSearchCriteria; onopen: (record: SavedSearchRecord) => void } = $props();
  let query = $state('');
  let editor = $state<'create' | 'edit' | null>(null);
  let editing = $state<SavedSearchRecord | null>(null);
  let confirmation = $state<Confirmation | null>(null);

  function openCreate(): void { editing = null; editor = 'create'; }
  function openEdit(record: SavedSearchRecord): void { editing = record; editor = 'edit'; }
  function requestReplace(record: SavedSearchRecord): void { confirmation = { action: 'replace', record }; }
  function requestDelete(record: SavedSearchRecord): void { confirmation = { action: 'delete', record }; }
  function closeConfirmation(): void { if (!controller.busy) confirmation = null; }

  async function save(name: string, description: string): Promise<void> {
    if (editor === 'edit' && editing) {
      if (await controller.update(editing.id, { name, description })) editor = null;
      return;
    }
    if (await controller.saveCurrent(name, description, currentCriteria)) editor = null;
  }

  async function confirmAction(): Promise<void> {
    if (!confirmation) return;
    const { action, record } = confirmation;
    const succeeded = action === 'replace'
      ? await controller.update(record.id, { criteria: currentCriteria })
      : await controller.delete(record.id);
    if (succeeded) confirmation = null;
  }
</script>

<V2Stack gap="md">
  {#if controller.error}<V2ErrorState title="Saved searches unavailable" message={controller.error} onretry={()=>void controller.refresh(query)}/>{/if}
  <V2OperationFeedback feedback={controller.feedback}/>
  <V2Toolbar sticky={false}>
    <V2Badge text={`${controller.records.length.toLocaleString()} saved searches`}/>
    <V2Badge text={controller.loading?'Loading…':controller.busy?'Saving…':'Ready'}/>
    {#snippet actions()}<V2Button variant="primary" disabled={controller.busy} onclick={openCreate}><Save size={17}/> Save current search</V2Button>{/snippet}
  </V2Toolbar>
  <V2Field label="Find saved searches" value={query} placeholder="Search by name or description…" onchange={(value)=>{query=value;void controller.refresh(value)}}/>
  {#if controller.records.length===0}
    <V2Card><span class="v2-muted">{controller.loading?'Loading saved searches…':'No saved searches match this view.'}</span></V2Card>
  {:else}
    <V2Stack gap="sm">
      {#each controller.records as record}
        <V2Card>
          <V2Inline justify="between" align="start" wrap>
            <V2Stack gap="xs"><b>{record.name}</b>{#if record.description}<span class="v2-small v2-muted">{record.description}</span>{/if}<span class="v2-small v2-muted">{record.criteria.mode==='expert'?'Expert':'Simple'} · updated {new Date(record.updatedAt).toLocaleString()}</span></V2Stack>
            <V2Inline gap="sm">
              <V2Button iconOnly title="Open saved search" ariaLabel={`Open ${record.name}`} disabled={controller.busy} onclick={()=>onopen(record)}><Play size={17}/></V2Button>
              <V2Button iconOnly title="Replace with current search" ariaLabel={`Replace ${record.name} criteria with current search`} disabled={controller.busy} onclick={()=>requestReplace(record)}><RefreshCw size={17}/></V2Button>
              <V2Button iconOnly title="Edit saved search" ariaLabel={`Edit ${record.name}`} disabled={controller.busy} onclick={()=>openEdit(record)}><Pencil size={17}/></V2Button>
              <V2Button iconOnly variant="danger" title="Delete saved search" ariaLabel={`Delete ${record.name}`} disabled={controller.busy} onclick={()=>requestDelete(record)}><Trash2 size={17}/></V2Button>
            </V2Inline>
          </V2Inline>
        </V2Card>
      {/each}
    </V2Stack>
  {/if}
</V2Stack>

{#if editor}<V2SavedSearchModal title={editor==='edit'?'Edit saved search':'Save current search'} name={editing?.name??''} description={editing?.description??''} busy={controller.busy} onclose={()=>editor=null} onsave={(name,description)=>void save(name,description)}/>{/if}

{#if confirmation}
  <ConfirmDialog
    title={confirmation.action === 'replace' ? 'Replace saved search criteria?' : 'Delete saved search?'}
    message={confirmation.action === 'replace'
      ? `Replace the stored criteria for “${confirmation.record.name}” with the current asset search?`
      : `Delete saved search “${confirmation.record.name}”?`}
    confirmLabel={confirmation.action === 'replace' ? 'Replace criteria' : 'Delete saved search'}
    icon={confirmation.action === 'replace' ? 'sync' : 'trash'}
    destructive={confirmation.action === 'delete'}
    busy={controller.busy}
    onconfirm={()=>void confirmAction()}
    onclose={closeConfirmation}
  />
{/if}
