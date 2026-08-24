import { describe, expect, it } from 'vitest';

import {
  anchoredScrollOffset,
  captureImageZoomAnchor,
  captureViewerPanOrigin,
  captureVisibleImageCenter,
  draggedScrollOffset,
  type ViewerRect,
} from './viewerZoom';

function rect(left: number, top: number, width: number, height: number): ViewerRect {
  return { left, top, right: left + width, bottom: top + height, width, height };
}

describe('viewer zoom anchors', () => {
  it('captures the normalized image pixel beneath the pointer', () => {
    expect(captureImageZoomAnchor(300, 250, rect(100, 50, 800, 400))).toEqual({
      clientX: 300,
      clientY: 250,
      imageX: 0.25,
      imageY: 0.5,
    });
    expect(captureImageZoomAnchor(50, 250, rect(100, 50, 800, 400))).toBeNull();
  });

  it('uses the center of only the visible image intersection', () => {
    expect(captureVisibleImageCenter(
      rect(-400, -200, 1200, 900),
      rect(0, 0, 600, 500),
    )).toEqual({
      clientX: 300,
      clientY: 250,
      imageX: 7 / 12,
      imageY: 0.5,
    });
  });

  it('compensates both scroll axes after zoom creates overflow', () => {
    const anchor = captureImageZoomAnchor(500, 350, rect(100, 50, 800, 600));
    expect(anchor).not.toBeNull();

    expect(anchoredScrollOffset(anchor!, rect(72, 16, 1200, 900), 0, 0)).toEqual({
      left: 172,
      top: 116,
    });
  });

  it('moves scroll offsets opposite to a captured drag gesture', () => {
    const origin = captureViewerPanOrigin(7, 400, 300, 260, 180);

    expect(draggedScrollOffset(origin, 340, 220)).toEqual({ left: 320, top: 260 });
    expect(draggedScrollOffset(origin, 800, 700)).toEqual({ left: 0, top: 0 });
  });
});
