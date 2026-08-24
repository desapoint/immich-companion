<script lang="ts">
  import AssetsPage from '../features/assets/components/AssetsPage.svelte';
  import StatusDashboard from '../features/status/components/StatusDashboard.svelte';
  import { errorMessage } from '../lib/utils/errors';
  import AppRuntimeError from './components/AppRuntimeError.svelte';
  import AppShell from './components/AppShell.svelte';

  const currentPath = window.location.pathname;
</script>

<svelte:boundary>
  <AppShell activePath={currentPath}>
    {#if currentPath === '/assets' || currentPath.startsWith('/assets/')}
      <AssetsPage />
    {:else}
      <StatusDashboard />
    {/if}
  </AppShell>

  {#snippet failed(error, reset)}
    <AppRuntimeError message={errorMessage(error)} onretry={reset} />
  {/snippet}
</svelte:boundary>
