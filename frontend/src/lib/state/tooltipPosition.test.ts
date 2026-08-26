import { describe, expect, it } from 'vitest';

import { calculateTooltipPosition } from './tooltipPosition';

const anchor = {
  top: 40,
  right: 140,
  bottom: 64,
  left: 116,
  width: 24,
  height: 24,
};

describe('calculateTooltipPosition', () => {
  it('places a tooltip below its anchor and clamps it inside the viewport', () => {
    expect(calculateTooltipPosition(anchor, 180, 28, 200, 240)).toEqual({
      left: 12,
      top: 70,
      placement: 'below',
    });
  });

  it('moves a tooltip above an anchor near the bottom edge', () => {
    expect(calculateTooltipPosition(
      { ...anchor, top: 200, bottom: 224 },
      80,
      30,
      320,
      240,
    )).toEqual({
      left: 88,
      top: 164,
      placement: 'above',
    });
  });
});
