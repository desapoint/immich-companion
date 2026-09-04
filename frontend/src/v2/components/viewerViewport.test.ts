import { describe, expect, it } from 'vitest';
import { actualSizeZoom, anchoredPan, clampPan, fitScale, renderedSize } from './viewerViewport';

describe('viewer viewport geometry', () => {
  it('computes contain-fit and actual-size zoom consistently', () => {
    expect(fitScale(400, 300, 800, 600)).toBe(0.5);
    expect(actualSizeZoom(400, 300, 800, 600)).toBe(2);
  });

  it('prevents panning when the rendered image fits the viewport', () => {
    const size = renderedSize(400, 300, 800, 600, 1);
    expect(clampPan(120, -80, size)).toEqual({ x: 0, y: 0 });
  });

  it('clamps pan to the visible image bounds when zoomed', () => {
    const size = renderedSize(400, 300, 800, 600, 2);
    expect(clampPan(500, -500, size)).toEqual({ x: 200, y: -150 });
  });

  it('keeps a zoom anchor stationary in viewport coordinates', () => {
    expect(anchoredPan(0, 0, 1, 2, 100, -50)).toEqual({ x: -100, y: 50 });
  });
});
