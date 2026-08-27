import { describe, expect, it } from 'vitest';
import { colorFromHex, hexToRgb, hslToHsv, hsvPointToValues, hsvToHsl, hsvToRgb, huePointToDegrees, normalizeHex, rgbToHex, rgbToHsv } from './colorMath';

describe('color math', () => {
  it('normalizes three and six digit HEX values', () => {
    expect(normalizeHex('fff')).toBe('#FFFFFF');
    expect(normalizeHex('#12abEf')).toBe('#12ABEF');
    expect(normalizeHex('not-a-color')).toBeNull();
  });

  it('round trips RGB and HEX', () => {
    expect(rgbToHex(hexToRgb('#275C4B'))).toBe('#275C4B');
  });

  it('round trips HSV and HSL without changing the color', () => {
    const hsv = rgbToHsv({ r: 39, g: 92, b: 75 });
    const rgb = hsvToRgb(hsv);
    expect(rgbToHex(rgb)).toBe('#275C4B');
    expect(hslToHsv(hsvToHsl(hsv))).toEqual(expect.objectContaining({ h: expect.any(Number) }));
  });

  it('maps visual control coordinates to hue and saturation/value', () => {
    expect(huePointToDegrees(50, 0, 100)).toBe(0);
    expect(huePointToDegrees(100, 50, 100)).toBe(90);
    expect(hsvPointToValues(0, 0, 100, 100)).toEqual({ s: 0, v: 100 });
    expect(hsvPointToValues(100, 100, 100, 100)).toEqual({ s: 100, v: 0 });
  });

  it('derives one consistent editable representation', () => {
    const value = colorFromHex('#336699');
    expect(value.hex).toBe('#336699'.toUpperCase());
    expect(value.rgb).toEqual({ r: 51, g: 102, b: 153 });
  });
});
