export const LOCAL_CHANGE_LABEL_FONT_PX = 11;
export const LOCAL_CHANGE_LABEL_MAX_WIDTH_PX = 29;
export const LOCAL_CHANGE_LABEL_HORIZONTAL_PADDING_PX = 4;
export const LOCAL_CHANGE_LABEL_VERTICAL_PADDING_PX = 2;
export const LOCAL_CHANGE_LABEL_LINE_HEIGHT_RATIO = 1.2;

export function clampLocalChangePercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
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
