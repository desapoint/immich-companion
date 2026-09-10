<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import V2Shell from './components/V2Shell.svelte';
  import V2ToastViewport from './components/V2ToastViewport.svelte';
  import V2ImplementationWarning from './components/V2ImplementationWarning.svelte';
  import V2AlbumsPage from './pages/V2AlbumsPage.svelte';
  import V2AssetsPage from './pages/V2AssetsPage.svelte';
  import V2DuplicatesPage from './pages/V2DuplicatesPage.svelte';
  import V2PlaygroundPage from './pages/V2PlaygroundPage.svelte';
  import V2RestorePage from './pages/V2RestorePage.svelte';
  import V2SettingsPage from './pages/V2SettingsPage.svelte';
  import V2StatusPage from './pages/V2StatusPage.svelte';
  import V2TagsPage from './pages/V2TagsPage.svelte';
  import { provideV2Toasts, V2ToastController } from './state/toasts.svelte';
  import { AssetSelectionWorkspaceController } from './state/assetSelectionWorkspace.svelte';
  import { TransientAssetSelectionController } from './state/transientAssetSelection.svelte';
  import { libraryData } from './data/currentDataSource.svelte';
  import {
    storeV2AssetFilterHandoff,
    v2PageFromLegacyHash,
    v2PageFromPath,
    v2PagePath,
    type V2AssetFilterHandoff,
    type V2PageKey,
  } from './navigation';
  import './styles/index.css';

  type NavItem = { key: V2PageKey; label: string; href: string; group?: string; position?: 'top' | 'bottom' };

  const navItems: NavItem[] = [
    { key: 'status', label: 'Status', href: v2PagePath('status'), group: 'Library' },
    { key: 'assets', label: 'Assets', href: v2PagePath('assets'), group: 'Library' },
    { key: 'restore', label: 'Restore', href: v2PagePath('restore'), group: 'Library' },
    { key: 'duplicates', label: 'Duplicates', href: v2PagePath('duplicates'), group: 'Library' },
    { key: 'albums', label: 'Albums', href: v2PagePath('albums'), group: 'Organize' },
    { key: 'tags', label: 'Tags', href: v2PagePath('tags'), group: 'Organize' },
    { key: 'settings', label: 'Settings', href: v2PagePath('settings'), position: 'bottom' },
    { key: 'docs', label: 'API Docs', href: v2PagePath('docs'), position: 'bottom' },
    { key: 'playground', label: 'Playground', href: v2PagePath('playground'), position: 'bottom' },
  ];

  const titles: Record<V2PageKey, string> = {
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

  function keyFromLocation(): V2PageKey {
    const legacyKey = v2PageFromLegacyHash(window.location.hash);
    if (legacyKey) {
      history.replaceState(null, '', v2PagePath(legacyKey));
      return legacyKey;
    }
    return v2PageFromPath(window.location.pathname);
  }

  let activeKey = $state<V2PageKey>(keyFromLocation());
  const assetSelection = new AssetSelectionWorkspaceController(libraryData.assets);
  const restoreSelection = new TransientAssetSelectionController();
  const toasts = provideV2Toasts(new V2ToastController());
  onDestroy(() => toasts.destroy());
  onMount(() => {
    document.body.classList.add('v2-active');
    return () => document.body.classList.remove('v2-active');
  });

  function navigate(key: string): void {
    const nextKey = key as V2PageKey;
    const path = v2PagePath(nextKey);
    if (window.location.pathname !== path || window.location.search || window.location.hash) {
      history.pushState(null, '', path);
    }
    activeKey = nextKey;
  }

  function openAssetsWithFilter(handoff: V2AssetFilterHandoff): void {
    storeV2AssetFilterHandoff(handoff);
    navigate('assets');
  }

  function syncFromLocation(): void {
    activeKey = keyFromLocation();
  }
</script>

<svelte:window onpopstate={syncFromLocation} />
<svelte:head><title>{titles[activeKey]} · Immich Companion V2</title></svelte:head>

<V2Shell {activeKey} title={titles[activeKey]} {navItems} onnavigate={navigate}>
  {#if activeKey === 'status'}
    <V2StatusPage />
  {:else if activeKey === 'assets'}
    <V2AssetsPage selectionWorkspace={assetSelection} />
  {:else if activeKey === 'restore'}
    <V2RestorePage selectionController={restoreSelection} />
  {:else if activeKey === 'duplicates'}
    <V2DuplicatesPage />
  {:else if activeKey === 'albums'}
    <V2AlbumsPage onfilterassets={(albumIds)=>openAssetsWithFilter({albumIds})}/>
  {:else if activeKey === 'tags'}
    <V2TagsPage onfilterassets={(tagIds)=>openAssetsWithFilter({tagIds})}/>
  {:else if activeKey === 'settings'}
    <V2SettingsPage toastPosition={toasts.position} ontoastpositionchange={(position)=>toasts.setPosition(position)} onopenplayground={()=>navigate('playground')}/>
  {:else if activeKey === 'playground'}
    <V2PlaygroundPage />
  {:else}
    <V2ImplementationWarning
      title={titles[activeKey]}
      description={`${titles[activeKey]} remains intentionally non-live in V2 while synchronization is implemented and validated. No backend action is available from this page yet.`}
    />
  {/if}
</V2Shell>
<V2ToastViewport controller={toasts}/>
