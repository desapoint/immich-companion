export type FloatingPlacement = 'down' | 'up';
export type FloatingAlignment = 'left' | 'right' | 'viewport';

export type FloatingLayoutInput = {
  anchor: Pick<DOMRect, 'left' | 'right' | 'top' | 'bottom' | 'width'>;
  viewportWidth: number;
  viewportHeight: number;
  preferredWidth: number;
  preferredHeight: number;
  minimumUsefulHeight?: number;
  minimumHeight?: number;
  gap?: number;
  margin?: number;
};

export type FloatingLayout = {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
  placement: FloatingPlacement;
  alignment: FloatingAlignment;
};

export function floatingFieldLayout({
  anchor,
  viewportWidth,
  viewportHeight,
  preferredWidth,
  preferredHeight,
  minimumUsefulHeight = 240,
  minimumHeight = 96,
  gap = 5,
  margin = 10,
}: FloatingLayoutInput): FloatingLayout {
  const usableWidth = Math.max(0, viewportWidth - margin * 2);
  const width = Math.min(Math.max(0, preferredWidth), usableWidth);
  const spaceBelow = Math.max(0, viewportHeight - anchor.bottom - gap - margin);
  const spaceAbove = Math.max(0, anchor.top - gap - margin);
  const placement: FloatingPlacement = spaceBelow >= Math.min(preferredHeight, minimumUsefulHeight) || spaceBelow >= spaceAbove ? 'down' : 'up';
  const availableHeight = placement === 'down' ? spaceBelow : spaceAbove;
  const maxHeight = Math.min(preferredHeight, Math.max(Math.min(minimumHeight, availableHeight), availableHeight));

  const leftAligned = anchor.left;
  const rightAligned = anchor.right - width;
  let left: number;
  let alignment: FloatingAlignment;
  if (leftAligned + width <= viewportWidth - margin) {
    left = Math.max(margin, leftAligned);
    alignment = 'left';
  } else if (rightAligned >= margin) {
    left = rightAligned;
    alignment = 'right';
  } else {
    left = Math.min(Math.max(leftAligned, margin), Math.max(margin, viewportWidth - width - margin));
    alignment = 'viewport';
  }

  const renderedHeight = Math.min(preferredHeight, maxHeight);
  return {
    top: placement === 'down' ? anchor.bottom + gap : Math.max(margin, anchor.top - gap - renderedHeight),
    left,
    width,
    maxHeight,
    placement,
    alignment,
  };
}
