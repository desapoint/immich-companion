<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import ApplicationShell from './components/ApplicationShell.svelte';
  import DocsPage from './components/DocsPage.svelte';
  import ToastViewport from '../lib/components/app/ToastViewport.svelte';
  import V2ImplementationWarning from '../lib/components/ui/ImplementationWarning.svelte';
  import StackConflictReviewHost from '../features/duplicates/components/StackConflictReviewHost.svelte';
  import DuplicateDestinationConflictReviewHost from '../features/duplicates/components/DuplicateDestinationConflictReviewHost.svelte';
  import AlbumsPage from '../features/albums/components/AlbumsPage.svelte';
  import V2AssetsPage from '../features/assets/components/AssetsPage.svelte';
  import DuplicatesPage from '../features/duplicates/components/DuplicatesPage.svelte';
  import ErrorHubPage from '../features/errors/components/ErrorHubPage.svelte';
  import SimilarityDebugPage from '../features/similarity-debug/components/SimilarityDebugPage.svelte';
  import PlaygroundPage from '../features/playground/components/PlaygroundPage.svelte';
  import V2RestorePage from '../features/assets/components/RestorePage.svelte';
  import SettingsPage from '../features/settings/components/SettingsPage.svelte';
  import StatusPage from '../features/status/components/StatusPage.svelte';
  import TagsPage from '../features/tags/components/TagsPage.svelte';
  import { provideToasts, ToastController } from './state/toasts.svelte';
  import { AssetSelectionWorkspaceController } from '../features/assets/state/assetSelectionWorkspace.svelte';
  import { TransientAssetSelectionController } from '../features/assets/state/transientAssetSelection.svelte';
  import { libraryData } from '../app/data/currentDataSource.svelte';
  import {
    storeAssetFilterHandoff,
    pageFromLegacyHash,
    pageFromPath,
    pagePath,
    type AssetFilterHandoff,
    type PageKey,
  } from './navigation';
  import '../styles/index.css';

  type NavItem = { key: PageKey; label: string; href: string; group?: string; position?: 'top' | 'bottom' };

  const navItems: NavItem[] = [
    { key: 'status', label: 'Status', href: pagePath('status'), group: 'Library' },
    { key: 'assets', label: 'Assets', href: pagePath('assets'), group: 'Library' },
    { key: 'restore', label: 'Trash', href: pagePath('restore'), group: 'Library' },
    { key: 'duplicates', label: 'Duplicates', href: pagePath('duplicates'), group: 'Library' },
    { key: 'albums', label: 'Albums', href: pagePath('albums'), group: 'Organize' },
    { key: 'tags', label: 'Tags', href: pagePath('tags'), group: 'Organize' },
    { key: 'errors', label: 'Error Hub', href: pagePath('errors'), group: 'Diagnostics' },
    { key: 'similarity-debug', label: 'Similarity debug', href: pagePath('similarity-debug'), group: 'Diagnostics' },
    { key: 'settings', label: 'Settings', href: pagePath('settings'), position: 'bottom' },
    { key: 'docs', label: 'API Docs', href: pagePath('docs'), position: 'bottom' },
    { key: 'playground', label: 'Playground', href: pagePath('playground'), position: 'bottom' },
  ];

  const titles: Record<PageKey, string> = {
    status: 'Status',
    errors: 'Error Hub',
    assets: 'Assets',
    restore: 'Trash',
    duplicates: 'Duplicates',
    'similarity-debug': 'Similarity debug',
    albums: 'Albums',
    tags: 'Tags',
    settings: 'Settings',
    docs: 'API Docs',
    playground: 'Playground',
  };

  function keyFromLocation(): PageKey {
    const legacyKey = pageFromLegacyHash(window.location.hash);
    if (legacyKey) {
      history.replaceState(null, '', pagePath(legacyKey));
      return legacyKey;
    }
    return pageFromPath(window.location.pathname);
  }

  let activeKey = $state<PageKey>(keyFromLocation());
  const assetSelection = new AssetSelectionWorkspaceController(libraryData.assets);
  const restoreSelection = new TransientAssetSelectionController();
  const toasts = provideToasts(new ToastController());
  onDestroy(() => toasts.destroy());
  onMount(() => {
    document.body.classList.add('v2-active');
    return () => document.body.classList.remove('v2-active');
  });

  function navigate(key: string): void {
    const nextKey = key as PageKey;
    const path = pagePath(nextKey);
    if (window.location.pathname !== path || window.location.search || window.location.hash) {
      history.pushState(null, '', path);
    }
    activeKey = nextKey;
  }

  function openAssetsWithFilter(handoff: AssetFilterHandoff): void {
    storeAssetFilterHandoff(handoff);
    navigate('assets');
  }

  function syncFromLocation(): void {
    activeKey = keyFromLocation();
  }
</script>

<svelte:window onpopstate={syncFromLocation} />
<svelte:head><title>{titles[activeKey]} · Immich Companion V2</title></svelte:head>

<ApplicationShell {activeKey} title={titles[activeKey]} {navItems} onnavigate={navigate}>
  {#if activeKey === 'status'}
    <StatusPage />
  {:else if activeKey === 'errors'}
    <ErrorHubPage />
  {:else if activeKey === 'assets'}
    <V2AssetsPage selectionWorkspace={assetSelection} />
  {:else if activeKey === 'restore'}
    <V2RestorePage selectionController={restoreSelection} />
  {:else if activeKey === 'duplicates'}
    <DuplicatesPage />
  {:else if activeKey === 'similarity-debug'}
    <SimilarityDebugPage />
  {:else if activeKey === 'albums'}
    <AlbumsPage onfilterassets={(albumIds)=>openAssetsWithFilter({albumIds})}/>
  {:else if activeKey === 'tags'}
    <TagsPage onfilterassets={(tagIds)=>openAssetsWithFilter({tagIds})}/>
  {:else if activeKey === 'settings'}
    <SettingsPage toastPosition={toasts.position} ontoastpositionchange={(position)=>toasts.setPosition(position)} onopenplayground={()=>navigate('playground')}/>
  {:else if activeKey === 'playground'}
    <PlaygroundPage />
  {:else if activeKey === 'docs'}
    <DocsPage />
  {:else}
    <V2ImplementationWarning
      title={titles[activeKey]}
      description={`${titles[activeKey]} remains intentionally non-live in V2 while synchronization is implemented and validated. No backend action is available from this page yet.`}
    />
  {/if}
</ApplicationShell>
<DuplicateDestinationConflictReviewHost />
<StackConflictReviewHost />
<ToastViewport controller={toasts}/>
