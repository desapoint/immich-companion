export const LOCAL_CHANGE_LABEL_MIN_FONT_PX = 10;
export const LOCAL_CHANGE_LABEL_MAX_FONT_PX = 12;
export const LOCAL_CHANGE_LABEL_HORIZONTAL_PADDING_PX = 4;
export const LOCAL_CHANGE_LABEL_VERTICAL_PADDING_PX = 2;
export const LOCAL_CHANGE_LABEL_LINE_HEIGHT_RATIO = 1.2;

export function clampLocalChangePercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function localChangeVisualPercent(actualChanged: number, emphasisFloor: number): number {
  const actual = clampLocalChangePercent(actualChanged);
  if (actual <= 0) return 0;
  return Math.max(actual, clampLocalChangePercent(emphasisFloor));
}

export function localChangeFillAlpha(actualChanged: number, emphasisFloor: number): number {
  const visual = localChangeVisualPercent(actualChanged, emphasisFloor);
  return visual <= 0 ? 0 : 0.08 + (visual / 100) * 0.5;
}

export function localChangeLabelFontSize(cellWidth: number, cellHeight: number): number {
  const preferred = Math.min(
    LOCAL_CHANGE_LABEL_MAX_FONT_PX,
    cellWidth * 0.32,
    cellHeight * 0.3,
  );
  return Math.max(LOCAL_CHANGE_LABEL_MIN_FONT_PX, preferred);
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
    || fontSize < LOCAL_CHANGE_LABEL_MIN_FONT_PX
  ) {
    return false;
  }

  const lineHeight = fontSize * LOCAL_CHANGE_LABEL_LINE_HEIGHT_RATIO;
  return (
    cellWidth >= measuredLabelWidth + LOCAL_CHANGE_LABEL_HORIZONTAL_PADDING_PX * 2
    && cellHeight >= lineHeight + LOCAL_CHANGE_LABEL_VERTICAL_PADDING_PX * 2
  );
}
