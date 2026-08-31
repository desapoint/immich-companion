<script lang="ts">
  import AssetsPage from '../features/assets/components/AssetsPage.svelte';
  import StatusDashboard from '../features/status/components/StatusDashboard.svelte';
  import SettingsPage from '../features/settings/components/SettingsPage.svelte';
  import { errorMessage } from '../lib/utils/errors';
  import AppRuntimeError from './components/AppRuntimeError.svelte';
  import AppShell from './components/AppShell.svelte';
  import AlbumsPage from '../features/relations/components/AlbumsPage.svelte';
  import TagsPage from '../features/relations/components/TagsPage.svelte';
  import RestorePage from '../features/assets/components/RestorePage.svelte';
  import DuplicatesPage from '../features/duplicates/components/DuplicatesPage.svelte';
  import DuplicateAssetViewerController from '../features/assets/components/DuplicateAssetViewerController.svelte';
  import type { DuplicatePreviewRequest } from '../features/duplicates/types/duplicates';

  const currentPath = window.location.pathname;
  let duplicatePreview = $state.raw<DuplicatePreviewRequest | null>(null);

  function openDuplicatePreview(request: DuplicatePreviewRequest): void {
    duplicatePreview = request;
  }
</script>

<svelte:boundary>
  <AppShell activePath={currentPath}>
    {#if currentPath === '/assets' || currentPath.startsWith('/assets/')}
      <AssetsPage />
    {:else if currentPath === '/albums'}
      <AlbumsPage />
    {:else if currentPath === '/tags'}
      <TagsPage />
    {:else if currentPath === '/restore'}
      <RestorePage />
    {:else if currentPath === '/duplicates'}
      <DuplicatesPage onpreview={openDuplicatePreview} />
    {:else}
      {#if currentPath === '/settings'}
        <SettingsPage />
      {:else}
        <StatusDashboard />
      {/if}
    {/if}
  </AppShell>

  {#if duplicatePreview}
    {#key duplicatePreview.group_id}
      <DuplicateAssetViewerController
        review={duplicatePreview}
        onclose={() => (duplicatePreview = null)}
      />
    {/key}
  {/if}

  {#snippet failed(error, reset)}
    <AppRuntimeError message={errorMessage(error)} onretry={reset} />
  {/snippet}
</svelte:boundary>
