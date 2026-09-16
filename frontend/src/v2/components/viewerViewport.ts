export type ViewportSize = {
  viewportW: number;
  viewportH: number;
  imageW: number;
  imageH: number;
};

export type Pan = { x: number; y: number };

export function fitScale(viewportW: number, viewportH: number, naturalW: number, naturalH: number): number {
  if (!viewportW || !viewportH || !naturalW || !naturalH) return 1;
  return Math.min(viewportW / naturalW, viewportH / naturalH) || 1;
}

export function renderedSize(
  viewportW: number,
  viewportH: number,
  naturalW: number,
  naturalH: number,
  zoom: number,
): ViewportSize | null {
  if (!viewportW || !viewportH || !naturalW || !naturalH) return null;
  const fit = fitScale(viewportW, viewportH, naturalW, naturalH);
  return {
    viewportW,
    viewportH,
    imageW: naturalW * fit * zoom,
    imageH: naturalH * fit * zoom,
  };
}

export function clampPan(panX: number, panY: number, size: ViewportSize | null): Pan {
  if (!size) return { x: panX, y: panY };
  const maxX = Math.abs(size.imageW - size.viewportW) / 2;
  const maxY = Math.abs(size.imageH - size.viewportH) / 2;
  return {
    x: maxX === 0 ? 0 : Math.max(-maxX, Math.min(maxX, panX)),
    y: maxY === 0 ? 0 : Math.max(-maxY, Math.min(maxY, panY)),
  };
}

export function anchoredPan(
  panX: number,
  panY: number,
  oldZoom: number,
  nextZoom: number,
  anchorX: number,
  anchorY: number,
): Pan {
  if (oldZoom === nextZoom) return { x: panX, y: panY };
  const ratio = nextZoom / oldZoom;
  return {
    x: anchorX - (anchorX - panX) * ratio,
    y: anchorY - (anchorY - panY) * ratio,
  };
}

export function actualSizeZoom(
  viewportW: number,
  viewportH: number,
  naturalW: number,
  naturalH: number,
  minZoom = 0.1,
  maxZoom = 8,
): number {
  const fit = fitScale(viewportW, viewportH, naturalW, naturalH);
  return Math.max(minZoom, Math.min(maxZoom, 1 / fit));
}
