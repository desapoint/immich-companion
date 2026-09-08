import { describe, expect, it } from 'vitest';

import { floatingFieldLayout } from './floatingField';

const anchor = { left: 100, right: 300, top: 100, bottom: 142, width: 200 };

describe('V2 floating field layout', () => {
  it('uses the room below and left-aligns when the popup fits', () => {
    expect(floatingFieldLayout({ anchor, viewportWidth: 1000, viewportHeight: 800, preferredWidth: 360, preferredHeight: 480 })).toMatchObject({ placement: 'down', alignment: 'left', top: 147, left: 100, width: 360, maxHeight: 480 });
  });

  it('uses the room above and positions the popup above its anchor', () => {
    const layout = floatingFieldLayout({ anchor: { ...anchor, top: 600, bottom: 642 }, viewportWidth: 1000, viewportHeight: 700, preferredWidth: 360, preferredHeight: 480 });
    expect(layout).toMatchObject({ placement: 'up', top: 115, maxHeight: 480 });
  });

  it('chooses the larger constrained side and clamps height', () => {
    const layout = floatingFieldLayout({ anchor: { ...anchor, top: 180, bottom: 222 }, viewportWidth: 500, viewportHeight: 360, preferredWidth: 360, preferredHeight: 480 });
    expect(layout.placement).toBe('up');
    expect(layout.maxHeight).toBe(165);
    expect(layout.top).toBe(10);
  });

  it('right-aligns near the right edge', () => {
    expect(floatingFieldLayout({ anchor: { ...anchor, left: 700, right: 900 }, viewportWidth: 920, viewportHeight: 800, preferredWidth: 360, preferredHeight: 480 })).toMatchObject({ alignment: 'right', left: 540 });
  });

  it('clamps width and position inside a small viewport', () => {
    expect(floatingFieldLayout({ anchor: { left: -20, right: 40, top: 100, bottom: 140, width: 60 }, viewportWidth: 300, viewportHeight: 500, preferredWidth: 360, preferredHeight: 480 })).toMatchObject({ alignment: 'left', left: 10, width: 280, maxHeight: 345 });
  });
});
