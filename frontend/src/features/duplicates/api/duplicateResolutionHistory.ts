import { requestJson, requestVoid } from '../../../lib/api/http';

export type DuplicateResolutionHistoryItem = {
  id: string;
  occurred_at: string;
  discovery_source: 'immich_duplicate' | 'companion_similarity';
  provider_group_id: string;
  review_status: 'reviewed_keep_all' | 'reviewed_resolve' | 'reviewed_stack_all' | 'reviewed_mixed';
  manual_action: string | null;
  member_count: number;
  member_asset_ids: string[];
};

type DuplicateResolutionHistoryPage = {
  items: DuplicateResolutionHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

type DuplicateResolutionHistoryClearAllResult = {
  cleared: number;
};

async function historyPage(page: number): Promise<DuplicateResolutionHistoryPage> {
  const params = new URLSearchParams({ page: String(page), page_size: '200' });
  return requestJson<DuplicateResolutionHistoryPage>(`/api/assets/duplicates/history?${params}`);
}

export async function duplicateResolutionHistoryDetail(
  resolutionId: string,
): Promise<DuplicateResolutionHistoryItem> {
  let page = 1;
  let pages = 1;
  do {
    const result = await historyPage(page);
    const match = result.items.find((item) => item.id === resolutionId);
    if (match) return match;
    pages = result.pages;
    page += 1;
  } while (page <= pages);
  throw new Error('The completed duplicate resolution was not found.');
}

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
