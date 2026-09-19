import { describe, expect, it } from 'vitest';
import { normalizedFocusFromPan, renderedSize } from '../state/viewportMath';
import { ViewerViewportController } from '../state/viewportController.svelte';

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

  it.each([2, 4])('preserves the exact raw transform across same-geometry single-pane replacements at %ix zoom', (zoom) => {
    const firstViewport = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(firstViewport.node);
    camera.setNaturalSize(1600, 1200);
    camera.setZoom(zoom);
    camera.panBy(-233.25, 117.5);
    const expected = {
      zoom: camera.zoom,
      panX: camera.panX,
      panY: camera.panY,
      transform: camera.transform,
    };

    for (let index = 0; index < 4; index += 1) {
      const replacement = fakeViewport(840, 600);
      camera.setViewport(null);
      camera.setViewport(replacement.node);

      expect(camera.zoom).toBe(expected.zoom);
      expect(camera.panX).toBe(expected.panX);
      expect(camera.panY).toBe(expected.panY);
      expect(camera.transform).toBe(expected.transform);
    }
  });

  it('preserves the logical target when comparison mode replaces the viewport with different geometry', () => {
    const sideBySide = fakeViewport(420, 600);
    const singlePane = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(sideBySide.node);
    camera.setNaturalSize(1600, 1200);
    camera.setZoom(4);
    camera.panBy(-240, 120);
    const before = cameraFocus(camera, 420, 600);
    const beforePan = { x: camera.panX, y: camera.panY };

    camera.setViewport(null);
    camera.setViewport(singlePane.node);
    const after = cameraFocus(camera, 840, 600);

    expect(camera.zoom).toBe(4);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y, 6);
    expect(camera.panX).not.toBe(beforePan.x);
    expect(camera.panY).not.toBe(beforePan.y);
  });

  it('keeps a letterboxed image at the same relative edge placement across mode changes', () => {
    const sideBySide = fakeViewport(420, 600);
    const singlePane = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(sideBySide.node);
    camera.setNaturalSize(600, 1600);
    camera.panBy(90, 0);

    const sideSize = renderedSize(420, 600, 600, 1600, camera.zoom)!;
    const sideTravel = Math.abs(sideSize.imageW - sideSize.viewportW) / 2;
    const initialPlacement = camera.panX / sideTravel;

    camera.setViewport(null);
    camera.setViewport(singlePane.node);

    const singleSize = renderedSize(840, 600, 600, 1600, camera.zoom)!;
    const singleTravel = Math.abs(singleSize.imageW - singleSize.viewportW) / 2;
    expect(camera.panX / singleTravel).toBeCloseTo(initialPlacement, 6);

    camera.setViewport(null);
    camera.setViewport(sideBySide.node);

    expect(camera.panX).toBeCloseTo(90, 6);
    expect(camera.panY).toBe(0);
  });

  it('does not walk a letterboxed image toward center after repeated comparison mode cycles', () => {
    const sideBySide = fakeViewport(420, 600);
    const singlePane = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(sideBySide.node);
    camera.setNaturalSize(1600, 600);
    camera.panBy(0, 200);
    const expectedPanY = camera.panY;

    for (let index = 0; index < 8; index += 1) {
      camera.setViewport(null);
      camera.setViewport(singlePane.node);
      camera.setViewport(null);
      camera.setViewport(sideBySide.node);
    }

    expect(camera.panX).toBe(0);
    expect(camera.panY).toBeCloseTo(expectedPanY, 6);
  });

  it('falls back to focal remapping when natural image geometry changes while the viewport is detached', () => {
    const firstViewport = fakeViewport(840, 600);
    const replacementViewport = fakeViewport(840, 600);
    const camera = new ViewerViewportController();
    camera.setViewport(firstViewport.node);
    camera.setNaturalSize(1600, 1200);
    camera.setZoom(4);
    camera.panBy(-240, 120);
    const before = cameraFocus(camera, 840, 600);
    const beforePan = { x: camera.panX, y: camera.panY };

    camera.setViewport(null);
    camera.setNaturalSize(1800, 1200);
    camera.setViewport(replacementViewport.node);
    const after = cameraFocus(camera, 840, 600);

    expect(camera.zoom).toBe(4);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y, 6);
    expect(camera.panX).not.toBe(beforePan.x);
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
