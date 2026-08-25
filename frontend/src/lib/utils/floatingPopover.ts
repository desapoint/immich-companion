export interface FloatingAnchorRect {
  left: number;
  right: number;
  top: number;
  bottom: number;
  width: number;
}

export interface FloatingPopoverLayout {
  placement: 'above' | 'below';
  left: number;
  width: number;
  top: number | null;
  bottom: number | null;
  maxHeight: number;
}

interface FloatingPopoverOptions {
  preferredWidth?: number;
  preferredHeight?: number;
  gap?: number;
  viewportPadding?: number;
}

export function floatingPopoverLayout(
  anchor: FloatingAnchorRect,
  viewportWidth: number,
  viewportHeight: number,
  options: FloatingPopoverOptions = {},
): FloatingPopoverLayout {
  const preferredWidth = options.preferredWidth ?? 384;
  const preferredHeight = options.preferredHeight ?? 320;
  const gap = options.gap ?? 6;
  const viewportPadding = options.viewportPadding ?? 12;
  const availableWidth = Math.max(0, viewportWidth - viewportPadding * 2);
  const width = Math.min(Math.max(anchor.width, preferredWidth), availableWidth);
  const left = Math.min(
    Math.max(viewportPadding, anchor.left),
    Math.max(viewportPadding, viewportWidth - viewportPadding - width),
  );
  const spaceBelow = Math.max(0, viewportHeight - anchor.bottom - gap - viewportPadding);
  const spaceAbove = Math.max(0, anchor.top - gap - viewportPadding);
  const placement = spaceBelow >= Math.min(preferredHeight, spaceAbove)
    ? 'below'
    : 'above';
  const maxHeight = placement === 'below' ? spaceBelow : spaceAbove;

  return {
    placement,
    left,
    width,
    top: placement === 'below' ? anchor.bottom + gap : null,
    bottom: placement === 'above' ? viewportHeight - anchor.top + gap : null,
    maxHeight,
  };
}
