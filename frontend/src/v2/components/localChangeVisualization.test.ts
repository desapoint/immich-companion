import { describe, expect, it } from 'vitest';
import {
  LOCAL_CHANGE_LABEL_MIN_FONT_PX,
  canRenderLocalChangeLabel,
  localChangeFillAlpha,
  localChangeLabelFontSize,
  localChangeVisualPercent,
} from './localChangeVisualization';

describe('localChangeVisualization', () => {
  it('keeps floor 0 identical to the current visual percentage', () => {
    expect(localChangeVisualPercent(5, 0)).toBe(5);
    expect(localChangeVisualPercent(50, 0)).toBe(50);
    expect(localChangeVisualPercent(80, 0)).toBe(80);
  });

  it('applies the emphasis floor only to positive cells', () => {
    expect(localChangeVisualPercent(0, 100)).toBe(0);
    expect(localChangeVisualPercent(5, 50)).toBe(50);
    expect(localChangeVisualPercent(50, 50)).toBe(50);
    expect(localChangeVisualPercent(80, 50)).toBe(80);
    expect(localChangeVisualPercent(5, 100)).toBe(100);
  });

  it('preserves the existing alpha mapping when the floor is zero', () => {
    expect(localChangeFillAlpha(0, 0)).toBe(0);
    expect(localChangeFillAlpha(5, 0)).toBeCloseTo(0.105);
    expect(localChangeFillAlpha(50, 0)).toBeCloseTo(0.33);
    expect(localChangeFillAlpha(100, 0)).toBeCloseTo(0.58);
  });

  it('uses emphasized display strength without changing zero cells', () => {
    expect(localChangeFillAlpha(0, 100)).toBe(0);
    expect(localChangeFillAlpha(5, 50)).toBeCloseTo(localChangeFillAlpha(50, 0));
    expect(localChangeFillAlpha(80, 50)).toBeCloseTo(localChangeFillAlpha(80, 0));
  });

  it('never shrinks labels below the readable minimum', () => {
    expect(localChangeLabelFontSize(8, 8)).toBe(LOCAL_CHANGE_LABEL_MIN_FONT_PX);
    expect(localChangeLabelFontSize(200, 200)).toBe(12);
  });

  it('suppresses labels when the CSS-space cell cannot contain readable text', () => {
    expect(canRenderLocalChangeLabel({
      cellWidth: 28,
      cellHeight: 15,
      measuredLabelWidth: 24,
      fontSize: 10,
    })).toBe(false);

    expect(canRenderLocalChangeLabel({
      cellWidth: 40,
      cellHeight: 20,
      measuredLabelWidth: 24,
      fontSize: 10,
    })).toBe(true);
  });

  it('requires readable height independently of available width', () => {
    expect(canRenderLocalChangeLabel({
      cellWidth: 100,
      cellHeight: 12,
      measuredLabelWidth: 24,
      fontSize: 10,
    })).toBe(false);
  });
});
