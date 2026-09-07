<script lang="ts">
  import V2Shell from './components/V2Shell.svelte';
  import V2ImplementationWarning from './components/V2ImplementationWarning.svelte';
  import V2SettingsPage from './pages/V2SettingsPage.svelte';
  import {
    v2PageFromLegacyHash,
    v2PageFromPath,
    v2PagePath,
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

  function navigate(key: string): void {
    const nextKey = key as V2PageKey;
    const path = v2PagePath(nextKey);
    if (window.location.pathname !== path || window.location.search || window.location.hash) {
      history.pushState(null, '', path);
    }
    activeKey = nextKey;
  }

  function syncFromLocation(): void {
    activeKey = keyFromLocation();
  }
</script>

<svelte:window onpopstate={syncFromLocation} />
<svelte:head><title>{titles[activeKey]} · Immich Companion V2</title></svelte:head>

<V2Shell {activeKey} title={titles[activeKey]} {navItems} onnavigate={navigate}>
  {#if activeKey === 'settings'}
    <V2SettingsPage />
  {:else}
    <V2ImplementationWarning
      title={titles[activeKey]}
      description={`${titles[activeKey]} remains intentionally non-live in V2 while synchronization is implemented and validated. No backend action is available from this page yet.`}
    />
  {/if}
</V2Shell>
