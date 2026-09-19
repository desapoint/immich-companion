import type { SelectionStorage } from './contracts';

export function defaultSelectionStorage(): SelectionStorage | null {
  return typeof sessionStorage === 'undefined' ? null : sessionStorage;
}

export function readSelectionId(storage: SelectionStorage | null, key: string): string | null {
  return storage?.getItem(key) || null;
}

export function persistSelectionId(storage: SelectionStorage | null, key: string, selectionId: string): void {
  storage?.setItem(key, selectionId);
}

export function clearSelectionId(storage: SelectionStorage | null, key: string): void {
  storage?.removeItem(key);
}
