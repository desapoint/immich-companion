export interface TooltipRect {
  top: number;
  right: number;
  bottom: number;
  left: number;
  width: number;
  height: number;
}
export interface TooltipPosition {
  left: number;
  top: number;
  placement: 'above' | 'below';
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

export function calculateTooltipPosition(
  anchor: TooltipRect,
  tooltipWidth: number,
  tooltipHeight: number,
  viewportWidth: number,
  viewportHeight: number,
  gap = 6,
  padding = 8,
): TooltipPosition {
  const spaceBelow = viewportHeight - anchor.bottom - padding;
  const spaceAbove = anchor.top - padding;
  const placement = spaceBelow >= tooltipHeight + gap || spaceBelow >= spaceAbove
    ? 'below'
    : 'above';
  const desiredTop = placement === 'below'
    ? anchor.bottom + gap
    : anchor.top - tooltipHeight - gap;
  const desiredLeft = anchor.left + anchor.width / 2 - tooltipWidth / 2;

  return {
    left: clamp(desiredLeft, padding, viewportWidth - tooltipWidth - padding),
    top: clamp(desiredTop, padding, viewportHeight - tooltipHeight - padding),
    placement,
  };
}
