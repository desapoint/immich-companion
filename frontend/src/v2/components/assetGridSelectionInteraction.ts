import { applyAssetRangeFromSnapshot, cloneAssetSelection, isAssetSelected, type AssetSelectionId, type AssetSelectionMode, type AssetSelectionState } from './assetSelection';

type Options<T extends AssetSelectionId> = {
  getItems: () => readonly T[];
  getSelection: () => AssetSelectionState<T>;
  setSelection: (selection: AssetSelectionState<T>) => void;
  parseAssetId: (value: string) => T | null;
  getScroller?: () => HTMLElement | null;
};

export function createAssetGridSelectionInteraction<T extends AssetSelectionId>(options: Options<T>) {
  let pointerCandidate = false, dragging = false;
  let startId: T | null = null, mode: AssetSelectionMode = 'add', snapshot: AssetSelectionState<T> | null = null;
  let startX = 0, startY = 0, pointerX = 0, pointerY = 0;
  let autoScrollFrame: number | null = null, suppressFrame: number | null = null, suppressedId: T | null = null;

  function idUnderPointer(x: number, y: number): T | null {
    const value = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-asset-id]')?.dataset.assetId;
    return value === undefined ? null : options.parseAssetId(value);
  }
  function applyRange(toId: T) {
    if (startId === null || snapshot === null) return;
    options.setSelection(applyAssetRangeFromSnapshot(snapshot, options.getItems(), startId, toId, mode));
  }
  function updateFromPointer() { const id = idUnderPointer(pointerX, pointerY); if (id !== null) applyRange(id); }
  function stopAutoScroll() { if (autoScrollFrame !== null) cancelAnimationFrame(autoScrollFrame); autoScrollFrame = null; }
  function autoScroll() {
    if (!dragging) { autoScrollFrame = null; return; }
    const scroller = options.getScroller?.() ?? document.querySelector<HTMLElement>('.v2-content');
    if (scroller) {
      const rect = scroller.getBoundingClientRect(), edge = 72;
      let delta = 0;
      if (pointerY < rect.top + edge) delta = -Math.ceil(((rect.top + edge - pointerY) / edge) * 18);
      else if (pointerY > rect.bottom - edge) delta = Math.ceil(((pointerY - (rect.bottom - edge)) / edge) * 18);
      if (delta) { scroller.scrollTop += delta; updateFromPointer(); }
    }
    autoScrollFrame = requestAnimationFrame(autoScroll);
  }
  function clearSuppressionSoon() {
    if (suppressFrame !== null) cancelAnimationFrame(suppressFrame);
    suppressFrame = requestAnimationFrame(() => { suppressedId = null; suppressFrame = null; });
  }
  function start(id: T, event: PointerEvent) {
    if (event.button !== 0 || event.pointerType === 'touch') return;
    pointerCandidate = true; dragging = false; suppressedId = null; startId = id;
    startX = pointerX = event.clientX; startY = pointerY = event.clientY;
    mode = isAssetSelected(options.getSelection(), id) ? 'remove' : 'add';
    snapshot = cloneAssetSelection(options.getSelection());
  }
  function move(event: PointerEvent) {
    if (!pointerCandidate || startId === null) return;
    pointerX = event.clientX; pointerY = event.clientY;
    if (!dragging) {
      if (Math.hypot(pointerX - startX, pointerY - startY) < 6) return;
      dragging = true;
      options.setSelection({ ...options.getSelection(), anchor: startId });
      document.body.classList.add('v2-range-selecting');
      if (autoScrollFrame === null) autoScrollFrame = requestAnimationFrame(autoScroll);
    }
    event.preventDefault(); updateFromPointer();
  }
  function finish() {
    const completed = dragging, completedStart = startId;
    if (completed && completedStart !== null) {
      const endId = idUnderPointer(pointerX, pointerY); if (endId !== null) applyRange(endId);
      options.setSelection({ ...options.getSelection(), anchor: completedStart });
      suppressedId = completedStart; clearSuppressionSoon();
    }
    pointerCandidate = false; dragging = false; startId = null; snapshot = null; stopAutoScroll(); document.body.classList.remove('v2-range-selecting');
  }
  function cancel() {
    if (dragging && snapshot !== null) options.setSelection(cloneAssetSelection(snapshot));
    pointerCandidate = false; dragging = false; startId = null; snapshot = null; suppressedId = null; stopAutoScroll(); document.body.classList.remove('v2-range-selecting');
  }
  function consumeSuppressedClick(id: T): boolean { if (suppressedId !== id) return false; suppressedId = null; return true; }
  function destroy() { stopAutoScroll(); if (suppressFrame !== null) cancelAnimationFrame(suppressFrame); document.body.classList.remove('v2-range-selecting'); }

  return { start, move, finish, cancel, consumeSuppressedClick, destroy, isDragging: () => dragging };
}
