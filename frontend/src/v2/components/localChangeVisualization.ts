export const LOCAL_CHANGE_LABEL_FONT_PX = 11;
export const LOCAL_CHANGE_LABEL_MAX_WIDTH_PX = 29;
export const LOCAL_CHANGE_LABEL_HORIZONTAL_PADDING_PX = 4;
export const LOCAL_CHANGE_LABEL_VERTICAL_PADDING_PX = 2;
export const LOCAL_CHANGE_LABEL_LINE_HEIGHT_RATIO = 1.2;

export const LOCAL_CHANGE_GRID_SIZES = [2, 4, 8, 16, 32] as const;
export type LocalChangeGridSize = (typeof LOCAL_CHANGE_GRID_SIZES)[number];

export type LocalChangeGrid = {
  rows: number;
  columns: number;
  cells: number[][];
};

export function clampLocalChangePercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function localChangeGridSizeForLevel(level: number): LocalChangeGridSize {
  const fallback = LOCAL_CHANGE_GRID_SIZES.length - 1;
  const rounded = Number.isFinite(level) ? Math.round(level) : fallback;
  const index = Math.max(0, Math.min(fallback, rounded));
  return LOCAL_CHANGE_GRID_SIZES[index];
}

export function aggregateLocalChangeGrid(
  cells: number[][],
  targetRows: number,
  targetColumns: number,
): LocalChangeGrid | null {
  const sourceRows = cells.length;
  const sourceColumns = sourceRows > 0 ? cells[0]?.length ?? 0 : 0;

  if (
    sourceRows <= 0
    || sourceColumns <= 0
    || !cells.every((row) => row.length === sourceColumns)
    || !Number.isInteger(targetRows)
    || !Number.isInteger(targetColumns)
    || targetRows <= 0
    || targetColumns <= 0
    || targetRows > sourceRows
    || targetColumns > sourceColumns
    || sourceRows % targetRows !== 0
    || sourceColumns % targetColumns !== 0
  ) {
    return null;
  }

  const rowStride = sourceRows / targetRows;
  const columnStride = sourceColumns / targetColumns;
  const valuesPerCell = rowStride * columnStride;
  const aggregated = Array.from({ length: targetRows }, (_, targetRow) =>
    Array.from({ length: targetColumns }, (_, targetColumn) => {
      let total = 0;
      const rowStart = targetRow * rowStride;
      const columnStart = targetColumn * columnStride;

      for (let sourceRow = rowStart; sourceRow < rowStart + rowStride; sourceRow += 1) {
        for (
          let sourceColumn = columnStart;
          sourceColumn < columnStart + columnStride;
          sourceColumn += 1
        ) {
          total += clampLocalChangePercent(cells[sourceRow][sourceColumn]);
        }
      }

      return total / valuesPerCell;
    }),
  );

  return {
    rows: targetRows,
    columns: targetColumns,
    cells: aggregated,
  };
}

export function localChangePassesVisibilityThreshold(actualChanged: number, minimumVisible: number): boolean {
  return clampLocalChangePercent(actualChanged) >= clampLocalChangePercent(minimumVisible);
}

export function localChangeVisualPercent(actualChanged: number, emphasisFloor: number): number {
  const actual = clampLocalChangePercent(actualChanged);
  if (actual <= 0) return 0;
  return Math.max(actual, clampLocalChangePercent(emphasisFloor));
}

export function localChangeFillAlpha(
  actualChanged: number,
  emphasisFloor: number,
  minimumVisible = 0,
): number {
  if (!localChangePassesVisibilityThreshold(actualChanged, minimumVisible)) return 0;
  const visual = localChangeVisualPercent(actualChanged, emphasisFloor);
  return visual <= 0 ? 0 : 0.08 + (visual / 100) * 0.5;
}

export function localChangeFillColor(color: string, alpha: number): string {
  const match = /^#([0-9a-f]{6})$/i.exec(color);
  const value = match?.[1] ?? '00DCFF';
  const safeAlpha = Number.isFinite(alpha) ? Math.max(0, Math.min(1, alpha)) : 0;
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${safeAlpha})`;
}

export function canRenderLocalChangeLabel({
  cellWidth,
  cellHeight,
  measuredLabelWidth,
  fontSize,
}: {
  cellWidth: number;
  cellHeight: number;
  measuredLabelWidth: number;
  fontSize: number;
}): boolean {
  if (
    !Number.isFinite(cellWidth)
    || !Number.isFinite(cellHeight)
    || !Number.isFinite(measuredLabelWidth)
    || !Number.isFinite(fontSize)
    || cellWidth <= 0
    || cellHeight <= 0
    || measuredLabelWidth < 0
    || fontSize <= 0
  ) {
    return false;
  }

  const lineHeight = fontSize * LOCAL_CHANGE_LABEL_LINE_HEIGHT_RATIO;
  return (
    cellWidth >= measuredLabelWidth + LOCAL_CHANGE_LABEL_HORIZONTAL_PADDING_PX * 2
    && cellHeight >= lineHeight + LOCAL_CHANGE_LABEL_VERTICAL_PADDING_PX * 2
  );
}
