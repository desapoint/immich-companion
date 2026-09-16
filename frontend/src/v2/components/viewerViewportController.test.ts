import { describe, expect, it } from 'vitest';
import { normalizedFocusFromPan, renderedSize } from './viewerViewport';
import { ViewerViewportController } from './viewerViewport.svelte';

function fakeViewport(initialWidth: number, initialHeight: number): { node: HTMLElement; resize: (width: number, height: number) => void } {
  let width = initialWidth;
  let height = initialHeight;
  const node = {
    getBoundingClientRect: () => ({
      width,
      height,
      left: 0,
      top: 0,
      right: width,
      bottom: height,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRect),
  } as HTMLElement;
  return {
    node,
    resize: (nextWidth: number, nextHeight: number) => {
      width = nextWidth;
      height = nextHeight;
    },
  };
}

function cameraFocus(camera: ViewerViewportController, width: number, height: number) {
  return normalizedFocusFromPan(
    camera.panX,
    camera.panY,
    renderedSize(width, height, camera.naturalWidth, camera.naturalHeight, camera.zoom),
  );
}

describe('ViewerViewportController persistent camera', () => {
  it('preserves zoom and focal position across viewport resize', () => {
    const viewport = fakeViewport(400, 300);
    const camera = new ViewerViewportController();
    camera.setViewport(viewport.node);
    camera.setNaturalSize(800, 600);
    camera.setZoom(2);
    camera.panBy(-100, 50);
    const before = cameraFocus(camera, 400, 300);

    viewport.resize(700, 350);
    camera.remapViewport();
    const after = cameraFocus(camera, 700, 350);

    expect(camera.zoom).toBe(2);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y, 6);
  });

  it('preserves the logical target when comparison mode replaces the viewport node', () => {
    const sideBySide = fakeViewport(420, 600);
    const singlePane = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(sideBySide.node);
    camera.setNaturalSize(1600, 1200);
    camera.setZoom(4);
    camera.panBy(-240, 120);
    const before = cameraFocus(camera, 420, 600);

    camera.setViewport(null);
    camera.setViewport(singlePane.node);
    const after = cameraFocus(camera, 840, 600);

    expect(camera.zoom).toBe(4);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y, 6);
  });

  it('preserves the focal position when a replacement source reports a new natural resolution', () => {
    const viewport = fakeViewport(600, 400);
    const camera = new ViewerViewportController();
    camera.setViewport(viewport.node);
    camera.setNaturalSize(1200, 800);
    camera.setZoom(3);
    camera.panBy(-180, 90);
    const before = cameraFocus(camera, 600, 400);

    camera.setNaturalSize(2400, 1600);
    const after = cameraFocus(camera, 600, 400);

    expect(camera.zoom).toBe(3);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y, 6);
  });

  it('fits only as an explicit reset after initialization', () => {
    const viewport = fakeViewport(600, 400);
    const camera = new ViewerViewportController();
    camera.setViewport(viewport.node);
    camera.setNaturalSize(1200, 800);
    camera.setZoom(3);
    camera.panBy(-150, 75);

    camera.fit();

    expect(camera.zoom).toBe(1);
    expect(camera.panX).toBe(0);
    expect(camera.panY).toBe(0);
  });
});
