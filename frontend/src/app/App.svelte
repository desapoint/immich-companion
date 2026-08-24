<script lang="ts">
  import AssetsPage from '../features/assets/components/AssetsPage.svelte';
  import StatusDashboard from '../features/status/components/StatusDashboard.svelte';
  import AppShell from './components/AppShell.svelte';

  const currentPath = window.location.pathname;
</script>

<AppShell activePath={currentPath}>
  {#if currentPath === '/assets' || currentPath.startsWith('/assets/')}
    <AssetsPage />
  {:else}
    <StatusDashboard />
  {/if}
</AppShell>
