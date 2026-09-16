type GridAnchor = {
  index: number;
  top: number;
};

function scrollContainerFor(grid: HTMLElement): HTMLElement | null {
  return grid.closest<HTMLElement>('.v2-content');
}

function visibleTopFor(grid: HTMLElement, scroller: HTMLElement): number {
  const scrollerTop = scroller.getBoundingClientRect().top;
  const previous = grid.previousElementSibling;
  if (!(previous instanceof HTMLElement) || !previous.classList.contains('v2-toolbar')) return scrollerTop;
  return Math.max(scrollerTop, previous.getBoundingClientRect().bottom);
}

export function createGridViewportAnchor(getGrid: () => HTMLElement | null) {
  let anchor: GridAnchor | null = null;
  let frame = 0;

  function begin(columns: number): void {
    if (anchor) return;

    const grid = getGrid();
    const scroller = grid ? scrollContainerFor(grid) : null;
    const first = grid?.firstElementChild;
    if (!grid || !scroller || !(first instanceof HTMLElement) || grid.children.length === 0) return;

    const gridRect = grid.getBoundingClientRect();
    const firstRect = first.getBoundingClientRect();
    const styles = getComputedStyle(grid);
    const rowGap = Number.parseFloat(styles.rowGap) || 0;
    const rowPitch = firstRect.height + rowGap;
    const visibleTop = visibleTopFor(grid, scroller);
    const offset = Math.max(0, visibleTop - gridRect.top);
    const row = rowPitch > 0 ? Math.floor((offset + rowGap) / rowPitch) : 0;
    const index = Math.min(grid.children.length - 1, row * Math.max(1, columns));
    const node = grid.children[index];
    if (!(node instanceof HTMLElement)) return;

    anchor = {
      index,
      top: node.getBoundingClientRect().top - visibleTop,
    };
  }

  function adjust(): void {
    const saved = anchor;
    if (!saved) return;

    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const grid = getGrid();
      const scroller = grid ? scrollContainerFor(grid) : null;
      const node = grid?.children[saved.index];
      if (!grid || !scroller || !(node instanceof HTMLElement)) return;

      const visibleTop = visibleTopFor(grid, scroller);
      const nextTop = node.getBoundingClientRect().top - visibleTop;
      const delta = nextTop - saved.top;
      if (Math.abs(delta) > 0.5) scroller.scrollTop += delta;
    });
  }

  function end(): void {
    adjust();
    anchor = null;
  }

  function destroy(): void {
    cancelAnimationFrame(frame);
    anchor = null;
  }

  return { begin, adjust, end, destroy };
}
