<script lang="ts">
  import AssetsPage from '../features/assets/components/AssetsPage.svelte';
  import StatusDashboard from '../features/status/components/StatusDashboard.svelte';
  import SettingsPage from '../features/settings/components/SettingsPage.svelte';
  import { errorMessage } from '../lib/utils/errors';
  import AppRuntimeError from './components/AppRuntimeError.svelte';
  import AppShell from './components/AppShell.svelte';
  import AlbumsPage from '../features/relations/components/AlbumsPage.svelte';
  import TagsPage from '../features/relations/components/TagsPage.svelte';

  const currentPath = window.location.pathname;
</script>

<svelte:boundary>
  <AppShell activePath={currentPath}>
    {#if currentPath === '/assets' || currentPath.startsWith('/assets/')}
      <AssetsPage />
    {:else if currentPath === '/albums'}
      <AlbumsPage />
    {:else if currentPath === '/tags'}
      <TagsPage />
    {:else}
      {#if currentPath === '/settings'}
        <SettingsPage />
      {:else}
        <StatusDashboard />
      {/if}
    {/if}
  </AppShell>

  {#snippet failed(error, reset)}
    <AppRuntimeError message={errorMessage(error)} onretry={reset} />
  {/snippet}
</svelte:boundary>
