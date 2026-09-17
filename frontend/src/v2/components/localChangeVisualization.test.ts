import { describe, expect, it } from 'vitest';
import {
  LOCAL_CHANGE_LABEL_FONT_PX,
  LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
  canRenderLocalChangeLabel,
  localChangeFillAlpha,
  localChangeFillColor,
  localChangePassesVisibilityThreshold,
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

  it('preserves the existing alpha mapping when both presentation controls are zero', () => {
    expect(localChangeFillAlpha(0, 0, 0)).toBe(0);
    expect(localChangeFillAlpha(5, 0, 0)).toBeCloseTo(0.105);
    expect(localChangeFillAlpha(50, 0, 0)).toBeCloseTo(0.33);
    expect(localChangeFillAlpha(100, 0, 0)).toBeCloseTo(0.58);
  });

  it('uses emphasized display strength without changing zero cells', () => {
    expect(localChangeFillAlpha(0, 100, 0)).toBe(0);
    expect(localChangeFillAlpha(5, 50, 0)).toBeCloseTo(localChangeFillAlpha(50, 0, 0));
    expect(localChangeFillAlpha(80, 50, 0)).toBeCloseTo(localChangeFillAlpha(80, 0, 0));
  });

  it('suppresses differences below the minimum visible threshold without changing the measured value', () => {
    expect(localChangePassesVisibilityThreshold(4.9, 5)).toBe(false);
    expect(localChangePassesVisibilityThreshold(5, 5)).toBe(true);
    expect(localChangePassesVisibilityThreshold(80, 5)).toBe(true);
    expect(localChangeFillAlpha(4.9, 100, 5)).toBe(0);
    expect(localChangeFillAlpha(5, 0, 5)).toBeCloseTo(0.105);
  });

  it('keeps the zero threshold equivalent to the previous visibility behavior', () => {
    expect(localChangePassesVisibilityThreshold(0, 0)).toBe(true);
    expect(localChangePassesVisibilityThreshold(1, 0)).toBe(true);
    expect(localChangeFillAlpha(5, 50)).toBeCloseTo(localChangeFillAlpha(50, 0));
  });

  it('combines the selected highlight color with the existing alpha mapping', () => {
    expect(localChangeFillColor('#00DCFF', 0)).toBe('rgba(0, 220, 255, 0)');
    expect(localChangeFillColor('#00DCFF', 0.58)).toBe('rgba(0, 220, 255, 0.58)');
    expect(localChangeFillColor('#FF0000', 0.33)).toBe('rgba(255, 0, 0, 0.33)');
    expect(localChangeFillColor('invalid', 2)).toBe('rgba(0, 220, 255, 1)');
  });

  it('uses one fixed readable label size and hides labels when a cell cannot contain it', () => {
    expect(LOCAL_CHANGE_LABEL_FONT_PX).toBe(11);
    expect(canRenderLocalChangeLabel({
      cellWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX + 7,
      cellHeight: 20,
      measuredLabelWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
      fontSize: LOCAL_CHANGE_LABEL_FONT_PX,
    })).toBe(false);

    expect(canRenderLocalChangeLabel({
      cellWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX + 8,
      cellHeight: 20,
      measuredLabelWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
      fontSize: LOCAL_CHANGE_LABEL_FONT_PX,
    })).toBe(true);
  });

  it('requires readable height independently of available width', () => {
    expect(canRenderLocalChangeLabel({
      cellWidth: 100,
      cellHeight: 17,
      measuredLabelWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
      fontSize: LOCAL_CHANGE_LABEL_FONT_PX,
    })).toBe(false);
    expect(canRenderLocalChangeLabel({
      cellWidth: 100,
      cellHeight: 18,
      measuredLabelWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
      fontSize: LOCAL_CHANGE_LABEL_FONT_PX,
    })).toBe(true);
  });
});
