import { describe, expect, it } from 'vitest';

import { floatingPopoverLayout } from './floatingPopover';

describe('floating popover layout', () => {
  it('uses the room below and clamps width inside the viewport', () => {
    const layout = floatingPopoverLayout(
      { left: 900, right: 1100, top: 100, bottom: 140, width: 200 },
      1024,
      800,
    );

    expect(layout).toMatchObject({
      placement: 'below',
      left: 628,
      width: 384,
      top: 146,
      bottom: null,
      maxHeight: 642,
    });
  });

  it('moves above near the viewport bottom and uses only available height', () => {
    const layout = floatingPopoverLayout(
      { left: 20, right: 260, top: 690, bottom: 730, width: 240 },
      900,
      760,
    );

    expect(layout).toMatchObject({
      placement: 'above',
      left: 20,
      top: null,
      bottom: 76,
      maxHeight: 672,
    });
  });

  it('shrinks to narrow viewports without crossing either edge', () => {
    const layout = floatingPopoverLayout(
      { left: 4, right: 204, top: 60, bottom: 100, width: 200 },
      280,
      360,
    );

    expect(layout.left).toBe(12);
    expect(layout.width).toBe(256);
    expect(layout.left + layout.width).toBe(268);
  });
});
