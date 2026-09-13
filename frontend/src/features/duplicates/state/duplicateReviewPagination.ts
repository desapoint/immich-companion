import type { DuplicateReviewProjection } from './duplicateReviewFilters';

export const DEFAULT_DUPLICATE_PAGE_SIZE = 12;
export const DUPLICATE_PAGE_SIZE_OPTIONS = [12, 24, 48] as const;

export function paginateDuplicateReviewEntries(
  entries: DuplicateReviewProjection[],
  requestedPage: number,
  pageSize: number,
): { page: number; pages: number; entries: DuplicateReviewProjection[] } {
  const pages = Math.ceil(entries.length / pageSize);
  const page = pages === 0 ? 1 : Math.min(Math.max(1, requestedPage), pages);
  return {
    page,
    pages,
    entries: entries.slice((page - 1) * pageSize, page * pageSize),
  };
}
