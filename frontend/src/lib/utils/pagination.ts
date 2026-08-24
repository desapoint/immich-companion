export interface PaginationWindowOptions {
  currentPage: number;
  totalPages: number;
  siblingCount?: number;
  boundaryCount?: number;
}

export type PaginationItem =
  | { kind: 'page'; page: number; key: string }
  | { kind: 'ellipsis'; key: string };

function positiveInteger(value: number, minimum = 0): number {
  if (!Number.isFinite(value)) return minimum;
  return Math.max(minimum, Math.floor(value));
}

function addRange(target: Set<number>, start: number, end: number): void {
  for (let page = start; page <= end; page += 1) target.add(page);
}

export function buildPaginationItems({
  currentPage,
  totalPages,
  siblingCount = 2,
  boundaryCount = 1,
}: PaginationWindowOptions): PaginationItem[] {
  const pages = positiveInteger(totalPages);
  if (pages === 0) return [];

  const current = Math.min(positiveInteger(currentPage, 1), pages);
  const siblings = positiveInteger(siblingCount);
  const boundaries = Math.min(positiveInteger(boundaryCount), pages);
  const windowSize = siblings * 2 + 1;
  let windowStart = current - siblings;
  let windowEnd = current + siblings;

  if (windowStart < 1) {
    windowStart = 1;
    windowEnd = Math.min(pages, windowSize);
  } else if (windowEnd > pages) {
    windowEnd = pages;
    windowStart = Math.max(1, pages - windowSize + 1);
  }

  const visiblePages = new Set<number>();
  addRange(visiblePages, 1, boundaries);
  addRange(visiblePages, windowStart, windowEnd);
  addRange(visiblePages, Math.max(1, pages - boundaries + 1), pages);

  const sortedPages = [...visiblePages].sort((left, right) => left - right);
  const items: PaginationItem[] = [];

  for (const page of sortedPages) {
    const previousPage = items.at(-1);
    const previousNumber = previousPage?.kind === 'page' ? previousPage.page : null;

    if (previousNumber !== null) {
      const gap = page - previousNumber;
      if (gap === 2) {
        const missingPage = previousNumber + 1;
        items.push({ kind: 'page', page: missingPage, key: `page-${missingPage}` });
      } else if (gap > 2) {
        items.push({ kind: 'ellipsis', key: `ellipsis-${previousNumber}-${page}` });
      }
    }

    items.push({ kind: 'page', page, key: `page-${page}` });
  }

  return items;
}
