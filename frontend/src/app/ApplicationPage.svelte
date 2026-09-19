<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import ApplicationShell from './components/ApplicationShell.svelte';
  import ToastViewport from '../lib/components/app/ToastViewport.svelte';
  import V2ImplementationWarning from '../lib/components/ui/ImplementationWarning.svelte';
  import V2StackConflictReviewHost from '../v2/components/V2StackConflictReviewHost.svelte';
  import V2AlbumsPage from '../v2/pages/V2AlbumsPage.svelte';
  import V2AssetsPage from '../v2/pages/V2AssetsPage.svelte';
  import DuplicatesPage from '../features/duplicates/components/DuplicatesPage.svelte';
  import PlaygroundPage from '../features/playground/components/PlaygroundPage.svelte';
  import V2RestorePage from '../v2/pages/V2RestorePage.svelte';
  import SettingsPage from '../features/settings/components/SettingsPage.svelte';
  import StatusPage from '../features/status/components/StatusPage.svelte';
  import V2TagsPage from '../v2/pages/V2TagsPage.svelte';
  import { provideToasts, ToastController } from './state/toasts.svelte';
  import { AssetSelectionWorkspaceController } from '../features/assets/state/assetSelectionWorkspace.svelte';
  import { TransientAssetSelectionController } from '../v2/state/transientAssetSelection.svelte';
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
    { key: 'restore', label: 'Restore', href: pagePath('restore'), group: 'Library' },
    { key: 'duplicates', label: 'Duplicates', href: pagePath('duplicates'), group: 'Library' },
    { key: 'albums', label: 'Albums', href: pagePath('albums'), group: 'Organize' },
    { key: 'tags', label: 'Tags', href: pagePath('tags'), group: 'Organize' },
    { key: 'settings', label: 'Settings', href: pagePath('settings'), position: 'bottom' },
    { key: 'docs', label: 'API Docs', href: pagePath('docs'), position: 'bottom' },
    { key: 'playground', label: 'Playground', href: pagePath('playground'), position: 'bottom' },
  ];

  const titles: Record<PageKey, string> = {
    status: 'Status',
    assets: 'Assets',
    restore: 'Restore',
    duplicates: 'Duplicates',
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
  {:else if activeKey === 'assets'}
    <V2AssetsPage selectionWorkspace={assetSelection} />
  {:else if activeKey === 'restore'}
    <V2RestorePage selectionController={restoreSelection} />
  {:else if activeKey === 'duplicates'}
    <DuplicatesPage />
  {:else if activeKey === 'albums'}
    <V2AlbumsPage onfilterassets={(albumIds)=>openAssetsWithFilter({albumIds})}/>
  {:else if activeKey === 'tags'}
    <V2TagsPage onfilterassets={(tagIds)=>openAssetsWithFilter({tagIds})}/>
  {:else if activeKey === 'settings'}
    <SettingsPage toastPosition={toasts.position} ontoastpositionchange={(position)=>toasts.setPosition(position)} onopenplayground={()=>navigate('playground')}/>
  {:else if activeKey === 'playground'}
    <PlaygroundPage />
  {:else}
    <V2ImplementationWarning
      title={titles[activeKey]}
      description={`${titles[activeKey]} remains intentionally non-live in V2 while synchronization is implemented and validated. No backend action is available from this page yet.`}
    />
  {/if}
</ApplicationShell>
<V2StackConflictReviewHost />
<ToastViewport controller={toasts}/>
