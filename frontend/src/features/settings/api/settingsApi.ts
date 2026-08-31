import type { SyncRuntimeSettings, SyncSchedule } from '../types/settings';
export { loadDuplicatePolicy, loadImmichLibraries, saveDuplicatePolicy } from '../../../lib/api/duplicatePolicyApi';

async function requestRuntimeSettings(
  method: 'GET' | 'PUT', value?: SyncRuntimeSettings,
): Promise<SyncRuntimeSettings> {
  const response = await fetch('/api/settings/sync/runtime', {
    method,
    headers: { accept: 'application/json', ...(value ? { 'content-type': 'application/json' } : {}) },
    ...(value ? { body: JSON.stringify(value) } : {}),
  });
  if (!response.ok) throw new Error(`Could not save global-sync load settings (${response.status}).`);
  return (await response.json()) as SyncRuntimeSettings;
}

export function loadSyncRuntimeSettings(): Promise<SyncRuntimeSettings> {
  return requestRuntimeSettings('GET');
}

export function saveSyncRuntimeSettings(value: SyncRuntimeSettings): Promise<SyncRuntimeSettings> {
  return requestRuntimeSettings('PUT', value);
}

export async function loadSyncSchedules(): Promise<SyncSchedule[]> {
  const response = await fetch('/api/settings/sync');
  if (!response.ok) throw new Error(`Could not load sync settings (${response.status}).`);
  return (await response.json()) as SyncSchedule[];
}

export async function saveSyncSchedule(
  name: string,
  value: Pick<SyncSchedule, 'enabled' | 'cron_expression'>,
): Promise<SyncSchedule> {
  const response = await fetch(`/api/settings/sync/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify(value),
  });
  if (!response.ok) throw new Error(`Could not save sync settings (${response.status}).`);
  return (await response.json()) as SyncSchedule;
}
