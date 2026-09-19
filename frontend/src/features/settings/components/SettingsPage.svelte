<script lang="ts">
  import { onMount } from 'svelte';
  import GeneralSettingsSection from './GeneralSettingsSection.svelte';
  import DuplicateSettingsSection from './DuplicateSettingsSection.svelte';
  import SyncSettingsSection from './SyncSettingsSection.svelte';
  import V2ActiveTasksSettings from '../../../v2/components/V2ActiveTasksSettings.svelte';
  import V2PageLayout from '../../../v2/components/V2PageLayout.svelte';
  import V2Notice from '../../../v2/components/V2Notice.svelte';
  import V2Section from '../../../v2/components/V2Section.svelte';
  import V2Tabs from '../../../v2/components/V2Tabs.svelte';
  import V2Toolbar from '../../../v2/components/V2Toolbar.svelte';
  import V2Zone from '../../../v2/components/V2Zone.svelte';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../../../v2/state/density';
  import { V2_TOAST_POSITIONS, type V2ToastPosition } from '../../../v2/state/toasts.svelte';

  type SettingsTab = 'General' | 'Duplicates' | 'Sync' | 'Tasks';
  let { toastPosition = 'top-right', ontoastpositionchange, onopenplayground }: { toastPosition?: V2ToastPosition; ontoastpositionchange?: (position: V2ToastPosition) => void; onopenplayground?: () => void } = $props();
  let tab = $state<SettingsTab>('General');
  let density = $state<V2Density>('standard');

  function setDensity(next: V2Density): void { density = next; writeV2Density(next); }

  onMount(() => {
    density = readV2Density();
    const onDensity = (event: Event) => density = (event as CustomEvent<V2Density>).detail;
    window.addEventListener(V2_DENSITY_EVENT, onDensity);
    return () => window.removeEventListener(V2_DENSITY_EVENT, onDensity);
  });
</script>

<V2PageLayout title="Settings" description="Configure interface behavior and live synchronization controls.">
  {#snippet tabs()}<V2Tabs items={['General', 'Duplicates', 'Sync', 'Tasks']} active={tab} ariaLabel="Settings sections" onselect={(value) => tab = value as SettingsTab} />{/snippet}
  <V2Zone>
    <V2Toolbar sticky={false}><b>{tab}</b></V2Toolbar>
    {#if tab === 'General'}
      <GeneralSettingsSection {density} {toastPosition} {ontoastpositionchange} {onopenplayground} ondensitychange={setDensity} />
    {:else if tab === 'Duplicates'}
      <DuplicateSettingsSection />
    {:else if tab === 'Tasks'}
      <V2ActiveTasksSettings />
    {:else}
      <SyncSettingsSection />
    {/if}
  </V2Zone>
</V2PageLayout>
