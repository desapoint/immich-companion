export interface ViewerRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
}

export interface ImageZoomAnchor {
  clientX: number;
  clientY: number;
  imageX: number;
  imageY: number;
}

export interface ViewerScrollOffset {
  left: number;
  top: number;
}

export interface ViewerPanOrigin {
  pointerId: number;
  clientX: number;
  clientY: number;
  scrollLeft: number;
  scrollTop: number;
}

export function captureImageZoomAnchor(
  clientX: number,
  clientY: number,
  imageRect: ViewerRect,
): ImageZoomAnchor | null {
  if (imageRect.width <= 0 || imageRect.height <= 0) return null;
  const imageX = (clientX - imageRect.left) / imageRect.width;
  const imageY = (clientY - imageRect.top) / imageRect.height;
  if (imageX < 0 || imageX > 1 || imageY < 0 || imageY > 1) return null;
  return { clientX, clientY, imageX, imageY };
}

export function captureVisibleImageCenter(
  imageRect: ViewerRect,
  viewportRect: ViewerRect,
): ImageZoomAnchor | null {
  const left = Math.max(imageRect.left, viewportRect.left);
  const top = Math.max(imageRect.top, viewportRect.top);
  const right = Math.min(imageRect.right, viewportRect.right);
  const bottom = Math.min(imageRect.bottom, viewportRect.bottom);
  if (right <= left || bottom <= top) return null;
  return captureImageZoomAnchor((left + right) / 2, (top + bottom) / 2, imageRect);
}

export function anchoredScrollOffset(
  anchor: ImageZoomAnchor,
  resizedImageRect: ViewerRect,
  currentLeft: number,
  currentTop: number,
): ViewerScrollOffset {
  const resizedClientX = resizedImageRect.left + anchor.imageX * resizedImageRect.width;
  const resizedClientY = resizedImageRect.top + anchor.imageY * resizedImageRect.height;
  return {
    left: Math.max(0, currentLeft + resizedClientX - anchor.clientX),
    top: Math.max(0, currentTop + resizedClientY - anchor.clientY),
  };
}

export function captureViewerPanOrigin(
  pointerId: number,
  clientX: number,
  clientY: number,
  scrollLeft: number,
  scrollTop: number,
): ViewerPanOrigin {
  return { pointerId, clientX, clientY, scrollLeft, scrollTop };
}

export function draggedScrollOffset(
  origin: ViewerPanOrigin,
  clientX: number,
  clientY: number,
): ViewerScrollOffset {
  return {
    left: Math.max(0, origin.scrollLeft - (clientX - origin.clientX)),
    top: Math.max(0, origin.scrollTop - (clientY - origin.clientY)),
  };
}
