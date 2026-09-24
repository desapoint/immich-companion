import { requestJson, requestVoid } from '../../../lib/api/http';

type DuplicateResolutionHistoryClearAllResult = {
  cleared: number;
};

export async function clearDuplicateResolutionHistory(resolutionId: string): Promise<void> {
  await requestVoid(
    `/api/assets/duplicates/history/${encodeURIComponent(resolutionId)}`,
    { method: 'DELETE' },
  );
}

export async function clearAllDuplicateResolutionHistory(): Promise<number> {
  const result = await requestJson<DuplicateResolutionHistoryClearAllResult>(
    '/api/assets/duplicates/history',
    { method: 'DELETE' },
  );
  return result.cleared;
}
