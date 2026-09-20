<script lang="ts">
  import GeneralSettingsSection from './GeneralSettingsSection.svelte';
  import DuplicateSettingsSection from './DuplicateSettingsSection.svelte';
  import SyncSettingsSection from './SyncSettingsSection.svelte';
  import V2ActiveTasksSettings from './ActiveTasksSettings.svelte';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Tabs from '../../../lib/components/ui/Tabs.svelte';
  import V2Toolbar from '../../../lib/components/layout/Toolbar.svelte';
  import V2Zone from '../../../lib/components/layout/Zone.svelte';
  import { TOAST_POSITIONS, type ToastPosition } from '../../../app/state/toasts.svelte';

  type SettingsTab = 'General' | 'Duplicates' | 'Sync' | 'Tasks';
  let { toastPosition = 'top-right', ontoastpositionchange, onopenplayground }: { toastPosition?: ToastPosition; ontoastpositionchange?: (position: ToastPosition) => void; onopenplayground?: () => void } = $props();
  let tab = $state<SettingsTab>('General');
  const tabDescription = $derived(tab === 'General' ? 'Interface preferences and local tools.' : tab === 'Duplicates' ? 'Duplicate sources and similarity tuning.' : tab === 'Sync' ? 'Run, schedule, and tune synchronization.' : 'Monitor and control background work.');
</script>

<V2PageLayout title="Settings" description="Configure interface behavior and live synchronization controls.">
  {#snippet tabs()}<V2Tabs items={['General', 'Duplicates', 'Sync', 'Tasks']} active={tab} ariaLabel="Settings sections" onselect={(value) => tab = value as SettingsTab} />{/snippet}
  <V2Zone>
    <V2Toolbar sticky={false}><div class="settings-tab-heading"><b>{tab}</b><span>{tabDescription}</span></div></V2Toolbar>
    {#if tab === 'General'}
      <GeneralSettingsSection {toastPosition} {ontoastpositionchange} {onopenplayground} />
    {:else if tab === 'Duplicates'}
      <DuplicateSettingsSection />
    {:else if tab === 'Tasks'}
      <V2ActiveTasksSettings />
    {:else}
      <SyncSettingsSection />
    {/if}
  </V2Zone>
</V2PageLayout>

<style>
  .settings-tab-heading{display:flex;align-items:baseline;gap:.65rem;min-width:0;flex-wrap:wrap}
  .settings-tab-heading span{color:var(--v2-muted);font-size:.78rem}
</style>
