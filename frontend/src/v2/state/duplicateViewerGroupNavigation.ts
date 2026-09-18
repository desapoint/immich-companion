export type DuplicateViewerGroupDirection = 'previous' | 'next';

export type DuplicateViewerGroupNavigationState = {
  resultMode: 'Pagination' | 'Infinite';
  page: number;
  pageSize: number;
  total: number;
  loadedCount: number;
  currentIndex: number;
  hasNextCursor: boolean;
};

export type DuplicateViewerGroupNavigationPlan =
  | { kind: 'loaded'; index: number }
  | { kind: 'page'; page: number; edge: 'first' | 'last' }
  | { kind: 'append'; index: number };

export function duplicateViewerGroupNavigationPlan(
  direction: DuplicateViewerGroupDirection,
  state: DuplicateViewerGroupNavigationState,
): DuplicateViewerGroupNavigationPlan | null {
  const { resultMode, total, loadedCount, currentIndex } = state;
  if (loadedCount < 1 || currentIndex < 0 || currentIndex >= loadedCount || total < 1) return null;

  if (direction === 'previous') {
    if (currentIndex > 0) return { kind: 'loaded', index: currentIndex - 1 };
    if (resultMode === 'Pagination' && state.page > 1) {
      return { kind: 'page', page: state.page - 1, edge: 'last' };
    }
    return null;
  }

  if (currentIndex < loadedCount - 1) return { kind: 'loaded', index: currentIndex + 1 };
  if (resultMode === 'Pagination') {
    const lastPage = Math.max(1, Math.ceil(total / Math.max(1, state.pageSize)));
    return state.page < lastPage
      ? { kind: 'page', page: state.page + 1, edge: 'first' }
      : null;
  }
  return state.hasNextCursor ? { kind: 'append', index: loadedCount } : null;
}
