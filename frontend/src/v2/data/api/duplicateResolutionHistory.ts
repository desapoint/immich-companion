import { requestVoid } from '../../../lib/api/http';

export async function clearDuplicateResolutionHistory(resolutionId: string): Promise<void> {
  await requestVoid(
    `/api/assets/duplicates/history/${encodeURIComponent(resolutionId)}`,
    { method: 'DELETE' },
  );
}
