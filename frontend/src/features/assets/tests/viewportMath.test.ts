import { describe, expect, it } from 'vitest';
import {
  actualSizeZoom,
  anchoredPan,
  clampPan,
  fitScale,
  normalizedFocusFromPan,
  panForNormalizedFocus,
  renderedSize,
} from '../state/viewportMath';

describe('viewer viewport geometry', () => {
  it('computes contain-fit and actual-size zoom consistently', () => {
    expect(fitScale(400, 300, 800, 600)).toBe(0.5);
    expect(actualSizeZoom(400, 300, 800, 600)).toBe(2);
  });

  it('keeps a fully occupied axis centered', () => {
    const size = renderedSize(400, 300, 800, 600, 1);
    expect(clampPan(120, -80, size)).toEqual({ x: 0, y: 0 });
  });

  it('allows a smaller image to move until its edge reaches the viewport boundary', () => {
    const size = renderedSize(400, 300, 800, 600, 0.5);
    expect(clampPan(500, -500, size)).toEqual({ x: 100, y: -75 });
  });

  it('clamps pan to the visible image bounds when zoomed beyond the viewport', () => {
    const size = renderedSize(400, 300, 800, 600, 2);
    expect(clampPan(500, -500, size)).toEqual({ x: 200, y: -150 });
  });

  it('keeps a zoom anchor stationary in viewport coordinates', () => {
    expect(anchoredPan(0, 0, 1, 2, 100, -50)).toEqual({ x: -100, y: 50 });
  });

  it('captures and restores the same normalized focal point across viewport geometry changes', () => {
    const before = renderedSize(400, 300, 800, 600, 2);
    const focus = normalizedFocusFromPan(-120, 60, before);
    const after = renderedSize(720, 420, 800, 600, 2);
    const restoredPan = panForNormalizedFocus(focus, after);
    const restoredFocus = normalizedFocusFromPan(restoredPan.x, restoredPan.y, after);

    expect(restoredFocus.x).toBeCloseTo(focus.x, 6);
    expect(restoredFocus.y).toBeCloseTo(focus.y, 6);
  });

  it('preserves focal position when natural resolution changes but aspect ratio stays the same', () => {
    const before = renderedSize(600, 400, 1200, 800, 3);
    const focus = normalizedFocusFromPan(-180, 90, before);
    const after = renderedSize(600, 400, 2400, 1600, 3);
    const restoredPan = panForNormalizedFocus(focus, after);
    const restoredFocus = normalizedFocusFromPan(restoredPan.x, restoredPan.y, after);

    expect(restoredFocus.x).toBeCloseTo(focus.x, 6);
    expect(restoredFocus.y).toBeCloseTo(focus.y, 6);
  });

  it('clamps to the closest valid focus when a new aspect ratio cannot preserve the old target exactly', () => {
    const before = renderedSize(400, 400, 1200, 600, 2);
    const focus = normalizedFocusFromPan(400, 0, before);
    const after = renderedSize(400, 400, 600, 1200, 2);
    const restoredPan = panForNormalizedFocus(focus, after);
    const restoredFocus = normalizedFocusFromPan(restoredPan.x, restoredPan.y, after);

    expect(restoredPan.x).toBe(0);
    expect(restoredFocus.x).toBe(0.5);
    expect(restoredFocus.y).toBeCloseTo(focus.y, 6);
  });

  it('preserves an off-center target from a side-by-side pane to a larger single-pane viewport', () => {
    const sideBySide = renderedSize(420, 600, 1600, 1200, 4);
    const focus = normalizedFocusFromPan(-260, 140, sideBySide);
    const singlePane = renderedSize(840, 600, 1600, 1200, 4);
    const restoredPan = panForNormalizedFocus(focus, singlePane);
    const restoredFocus = normalizedFocusFromPan(restoredPan.x, restoredPan.y, singlePane);

    expect(restoredFocus.x).toBeCloseTo(focus.x, 6);
    expect(restoredFocus.y).toBeCloseTo(focus.y, 6);
  });
});
