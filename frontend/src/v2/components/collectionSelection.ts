export type VisibleSelectionState = 'none' | 'some' | 'all';

export function visibleSelectionState(
  selectedIds: readonly string[],
  visibleIds: readonly string[],
): VisibleSelectionState {
  if (!visibleIds.length) return 'none';
  const selected = new Set(selectedIds);
  const selectedVisible = visibleIds.filter((id) => selected.has(id)).length;
  if (selectedVisible === 0) return 'none';
  return selectedVisible === visibleIds.length ? 'all' : 'some';
}

export function toggleVisibleSelection(
  selectedIds: readonly string[],
  visibleIds: readonly string[],
): string[] {
  if (!visibleIds.length) return [...selectedIds];
  const selected = new Set(selectedIds);
  if (visibleIds.every((id) => selected.has(id))) {
    for (const id of visibleIds) selected.delete(id);
  } else {
    for (const id of visibleIds) selected.add(id);
  }
  return [...selected];
}
