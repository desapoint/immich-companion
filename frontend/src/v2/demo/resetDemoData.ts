import { resetDemoAssetState } from './demoAssetState.svelte';

const DEMO_STORAGE_PREFIX = 'immichCompanionV2Demo';

function clearDemoStorage(storage: Storage): void {
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(DEMO_STORAGE_PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
}

/**
 * Restores every V2 demo-owned data store to its seeded state.
 *
 * The asset state is reset in memory immediately. Other demo repositories
 * (duplicates, saved searches, and future demo stores using the shared
 * storage prefix) are cleared from browser persistence and are recreated
 * from their canonical seeds on the reload performed by the shell.
 */
export function resetAllDemoData(): void {
  resetDemoAssetState();
  if (typeof sessionStorage !== 'undefined') clearDemoStorage(sessionStorage);
  if (typeof localStorage !== 'undefined') clearDemoStorage(localStorage);
}
