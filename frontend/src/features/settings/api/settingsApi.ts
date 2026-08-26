import type { SyncSchedule } from '../types/settings';

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
