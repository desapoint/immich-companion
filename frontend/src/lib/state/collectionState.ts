import type { PageResult } from '../types/collection';

export interface CollectionState<T> {
  items: T[];
  page: number;
  pageSize: number;
  pages: number;
  total: number;
  hasLoaded: boolean;
  initialLoading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  error: string | null;
}

export interface CollectionLoadRequest {
  page: number;
  pageSize: number;
  signal: AbortSignal;
}

export interface CollectionController<T> {
  load(page?: number): Promise<boolean>;
  reload(): Promise<boolean>;
  reset(): Promise<boolean>;
  changePage(page: number): Promise<boolean>;
  changePageSize(pageSize: number): Promise<boolean>;
  loadNextPage(): Promise<boolean>;
  clearError(): void;
  dispose(): void;
}

interface CollectionControllerOptions<T> {
  getKey?: (item: T) => string;
  fallbackError?: string;
}

export function createCollectionState<T>(pageSize: number): CollectionState<T> {
  return {
    items: [],
    page: 1,
    pageSize,
    pages: 0,
    total: 0,
    hasLoaded: false,
    initialLoading: false,
    refreshing: false,
    loadingMore: false,
    error: null,
  };
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function collectionHasMore<T>(state: CollectionState<T>): boolean {
  return state.hasLoaded && state.page < state.pages;
}

export function createCollectionController<T>(
  state: CollectionState<T>,
  loadPage: (request: CollectionLoadRequest) => Promise<PageResult<T>>,
  options: CollectionControllerOptions<T> = {},
): CollectionController<T> {
  let activeController: AbortController | null = null;
  let generation = 0;
  const fallbackError = options.fallbackError ?? 'Could not load this collection.';

  function startRequest(): { controller: AbortController; generation: number } {
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    generation += 1;
    return { controller, generation };
  }

  function applyResult(result: PageResult<T>): void {
    state.items = result.items;
    state.page = result.pages === 0 ? 1 : result.page;
    state.pageSize = result.pageSize;
    state.pages = result.pages;
    state.total = result.total;
    state.hasLoaded = true;
  }

  async function load(requestedPage = state.page): Promise<boolean> {
    const request = startRequest();
    const wasLoaded = state.hasLoaded;
    state.error = null;
    state.initialLoading = !wasLoaded;
    state.refreshing = wasLoaded;
    state.loadingMore = false;

    try {
      let result = await loadPage({
        page: Math.max(1, requestedPage),
        pageSize: state.pageSize,
        signal: request.controller.signal,
      });
      if (request.controller.signal.aborted || request.generation !== generation) return false;

      if (result.pages > 0 && requestedPage > result.pages) {
        result = await loadPage({
          page: result.pages,
          pageSize: state.pageSize,
          signal: request.controller.signal,
        });
        if (request.controller.signal.aborted || request.generation !== generation) return false;
      }

      applyResult(result);
      return true;
    } catch (error) {
      if (request.controller.signal.aborted || request.generation !== generation) return false;
      if (error instanceof DOMException && error.name === 'AbortError') return false;
      state.error = errorMessage(error, fallbackError);
      return false;
    } finally {
      if (request.generation === generation) {
        state.initialLoading = false;
        state.refreshing = false;
      }
    }
  }

  async function loadNextPage(): Promise<boolean> {
    if (!collectionHasMore(state) || state.initialLoading || state.refreshing || state.loadingMore) {
      return false;
    }

    const request = startRequest();
    state.loadingMore = true;
    state.error = null;
    try {
      const result = await loadPage({
        page: state.page + 1,
        pageSize: state.pageSize,
        signal: request.controller.signal,
      });
      if (request.controller.signal.aborted || request.generation !== generation) return false;

      const existingKeys = options.getKey
        ? new Set(state.items.map((item) => options.getKey!(item)))
        : null;
      const appended = existingKeys
        ? result.items.filter((item) => !existingKeys.has(options.getKey!(item)))
        : result.items;

      state.items = [...state.items, ...appended];
      state.page = result.page;
      state.pageSize = result.pageSize;
      state.pages = result.pages;
      state.total = result.total;
      state.hasLoaded = true;
      return true;
    } catch (error) {
      if (request.controller.signal.aborted || request.generation !== generation) return false;
      if (error instanceof DOMException && error.name === 'AbortError') return false;
      state.error = errorMessage(error, fallbackError);
      return false;
    } finally {
      if (request.generation === generation) state.loadingMore = false;
    }
  }

  return {
    load,
    reload: () => load(state.page),
    reset: () => load(1),
    changePage: (page) => load(page),
    changePageSize: (pageSize) => {
      if (!Number.isInteger(pageSize) || pageSize <= 0) return Promise.resolve(false);
      state.pageSize = pageSize;
      return load(1);
    },
    loadNextPage,
    clearError: () => {
      state.error = null;
    },
    dispose: () => {
      generation += 1;
      activeController?.abort();
      activeController = null;
      state.initialLoading = false;
      state.refreshing = false;
      state.loadingMore = false;
    },
  };
}
