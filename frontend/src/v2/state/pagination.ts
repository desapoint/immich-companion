export type PaginationItem =
  | { kind: 'page'; page: number }
  | { kind: 'gap'; from: number; to: number };

export function validPageNumber(value: string, maxPage: number): number | null {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const page = Number(trimmed);
  return Number.isSafeInteger(page) && page >= 1 && page <= Math.max(1, Math.floor(maxPage)) ? page : null;
}

export function paginationItems(currentPage: number, maxPage: number, radius = 3): PaginationItem[] {
  const last = Math.max(1, Math.floor(maxPage));
  const current = Math.min(last, Math.max(1, Math.floor(currentPage)));
  const resolvedRadius = Math.max(0, Math.floor(radius));
  const included = new Set<number>([1, last]);
  for (let page = current - resolvedRadius; page <= current + resolvedRadius; page += 1) {
    if (page >= 1 && page <= last) included.add(page);
  }
  const pages = [...included].sort((left, right) => left - right);
  const items: PaginationItem[] = [];
  for (const page of pages) {
    const previous = items.at(-1);
    if (previous?.kind === 'page') {
      const hidden = page - previous.page - 1;
      if (hidden === 1) items.push({ kind: 'page', page: previous.page + 1 });
      else if (hidden > 1) items.push({ kind: 'gap', from: previous.page + 1, to: page - 1 });
    }
    items.push({ kind: 'page', page });
  }
  return items;
}
