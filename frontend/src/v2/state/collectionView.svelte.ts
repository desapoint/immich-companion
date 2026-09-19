export type CollectionResultMode = 'Pagination' | 'Infinite';

export type CollectionViewOptions = {
  pageSize?: number;
  resultMode?: CollectionResultMode;
  loaded?: number;
  columns?: number;
  resultModeStorageKey?: string;
};

export function createCollectionView(options: CollectionViewOptions = {}) {
  let page = $state(1);
  let pageSize = $state(options.pageSize ?? 24);
  let resultMode = $state<CollectionResultMode>(options.resultMode ?? 'Pagination');
  let loaded = $state(options.loaded ?? options.pageSize ?? 24);
  let columns = $state(options.columns ?? 4);

  function persistResultMode(): void {
    if (!options.resultModeStorageKey || typeof localStorage === 'undefined') return;
    localStorage.setItem(options.resultModeStorageKey, resultMode === 'Pagination' ? 'paged' : 'infinite');
  }

  function hydrate(): void {
    if (!options.resultModeStorageKey || typeof localStorage === 'undefined') return;
    const stored = localStorage.getItem(options.resultModeStorageKey);
    if (stored === 'infinite') {
      resultMode = 'Infinite';
      loaded = Math.max(pageSize, loaded);
    } else if (stored === 'paged') {
      resultMode = 'Pagination';
    }
  }

  function setPage(next: number): void {
    page = Math.max(1, Math.floor(next));
  }

  function setPageSize(next: number, total?: number): void {
    const normalized = Math.max(1, Math.floor(next));
    pageSize = normalized;
    page = 1;
    loaded = total === undefined
      ? Math.max(normalized, loaded)
      : Math.max(normalized, Math.min(loaded, total));
  }

  function setMode(mode: CollectionResultMode): void {
    resultMode = mode;
    if (mode === 'Pagination') page = 1;
    else loaded = Math.max(pageSize, loaded);
    persistResultMode();
  }

  function setColumns(next: number | string): void {
    columns = Math.max(1, Math.floor(Number(next)));
  }

  function firstIndex(): number {
    return resultMode === 'Pagination' ? (page - 1) * pageSize : 0;
  }

  function visibleCount(total: number): number {
    if (resultMode === 'Infinite') return Math.min(loaded, total);
    return Math.min(pageSize, Math.max(0, total - firstIndex()));
  }

  function loadMore(total: number): void {
    loaded = Math.min(total, loaded + pageSize);
  }

  function clampPage(total: number): void {
    const lastPage = Math.max(1, Math.ceil(total / pageSize));
    page = Math.min(page, lastPage);
  }

  function reset(): void {
    page = 1;
    loaded = pageSize;
  }

  return {
    get page() { return page; },
    get pageSize() { return pageSize; },
    get resultMode() { return resultMode; },
    get loaded() { return loaded; },
    get columns() { return columns; },
    hydrate,
    setPage,
    setPageSize,
    setMode,
    setColumns,
    firstIndex,
    visibleCount,
    loadMore,
    clampPage,
    reset,
  };
}
