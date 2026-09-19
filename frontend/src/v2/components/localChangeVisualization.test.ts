import { describe, expect, it } from 'vitest';
import {
  LOCAL_CHANGE_LABEL_FONT_PX,
  LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
  aggregateLocalChangeGrid,
  canRenderLocalChangeLabel,
  localChangeFillAlpha,
  localChangeFillColor,
  localChangeGridSizeForLevel,
  localChangePassesVisibilityThreshold,
  localChangeVisualPercent,
} from './localChangeVisualization';

describe('localChangeVisualization', () => {
  it('maps the grid-detail slider to the supported coarse-to-fine sizes', () => {
    expect(localChangeGridSizeForLevel(0)).toBe(2);
    expect(localChangeGridSizeForLevel(1)).toBe(4);
    expect(localChangeGridSizeForLevel(2)).toBe(8);
    expect(localChangeGridSizeForLevel(3)).toBe(16);
    expect(localChangeGridSizeForLevel(4)).toBe(32);
    expect(localChangeGridSizeForLevel(-20)).toBe(2);
    expect(localChangeGridSizeForLevel(20)).toBe(32);
    expect(localChangeGridSizeForLevel(Number.NaN)).toBe(32);
  });

  it('aggregates fine Local Changes cells into larger coarse cells by mean changed percentage', () => {
    const aggregated = aggregateLocalChangeGrid([
      [0, 10, 20, 30],
      [10, 20, 30, 40],
      [40, 50, 60, 70],
      [50, 60, 70, 80],
    ], 2, 2);

    expect(aggregated).toEqual({
      rows: 2,
      columns: 2,
      cells: [
        [10, 30],
        [50, 70],
      ],
    });
  });

  it('supports every manual grid size derived from the native 32 by 32 diagnostics grid', () => {
    const source = Array.from({ length: 32 }, (_, row) =>
      Array.from({ length: 32 }, (_, column) => (row + column) % 100),
    );

    for (const target of [2, 4, 8, 16, 32]) {
      const aggregated = aggregateLocalChangeGrid(source, target, target);
      expect(aggregated?.rows).toBe(target);
      expect(aggregated?.columns).toBe(target);
      expect(aggregated?.cells).toHaveLength(target);
      expect(aggregated?.cells.every((row) => row.length === target)).toBe(true);
    }
  });

  it('clamps source percentages before coarse aggregation', () => {
    expect(aggregateLocalChangeGrid([
      [-10, 50],
      [150, Number.NaN],
    ], 1, 1)?.cells).toEqual([[37.5]]);
  });

  it('rejects unsupported aggregation shapes instead of inventing cells', () => {
    expect(aggregateLocalChangeGrid([
      [0, 10, 20, 30],
      [10, 20, 30, 40],
      [40, 50, 60, 70],
      [50, 60, 70, 80],
    ], 3, 3)).toBeNull();
  });

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
