import { describe, expect, it } from 'vitest';

import {
  addRecentColor,
  foregroundForBackground,
  hexToRgb,
  hsvToRgb,
  normalizeHex,
  parseRecentColors,
  relativeLuminance,
  rgbToHex,
  rgbToHsv,
  wrapHue,
} from './color';

describe('V2 color utilities', () => {
  it.each([
    ['#fff', '#FFFFFF'], ['fff', '#FFFFFF'], ['#FFFFFF', '#FFFFFF'], ['ffffff', '#FFFFFF'], ['#9a78ff', '#9A78FF'],
  ])('normalizes %s', (input, expected) => expect(normalizeHex(input)).toBe(expected));

  it.each(['#12', '#1234', 'red', 'hsl(0 0% 0%)', '', '#GGGGGG'])('rejects invalid HEX %s', (input) => {
    expect(normalizeHex(input)).toBeNull();
  });

  it.each([
    ['#FF0000', { r: 255, g: 0, b: 0 }],
    ['#00FF00', { r: 0, g: 255, b: 0 }],
    ['#0000FF', { r: 0, g: 0, b: 255 }],
    ['#FFFFFF', { r: 255, g: 255, b: 255 }],
    ['#000000', { r: 0, g: 0, b: 0 }],
    ['#808080', { r: 128, g: 128, b: 128 }],
    ['#9A78FF', { r: 154, g: 120, b: 255 }],
  ])('converts %s between RGB and HEX', (hex, rgb) => {
    expect(hexToRgb(hex)).toEqual(rgb);
    expect(rgbToHex(rgb)).toBe(hex);
  });

  it.each(['#FF0000', '#00FF00', '#0000FF', '#FFFFFF', '#000000', '#808080', '#9A78FF'])('round-trips %s through HSV', (hex) => {
    expect(rgbToHex(hsvToRgb(rgbToHsv(hexToRgb(hex))))).toBe(hex);
  });

  it('wraps hue and clamps saturation and value', () => {
    expect(wrapHue(-1)).toBe(359);
    expect(wrapHue(360)).toBe(0);
    expect(rgbToHex(hsvToRgb({ h: 720, s: 150, v: 150 }))).toBe('#FF0000');
    expect(rgbToHex(hsvToRgb({ h: 0, s: -10, v: -5 }))).toBe('#000000');
  });

  it('chooses a contrasting foreground from relative luminance', () => {
    expect(relativeLuminance('#FFFFFF')).toBeCloseTo(1);
    expect(relativeLuminance('#000000')).toBe(0);
    expect(foregroundForBackground('#FFFFFF')).toBe('#000000');
    expect(foregroundForBackground('#000000')).toBe('#FFFFFF');
    expect(foregroundForBackground('#EAB308')).toBe('#000000');
    expect(foregroundForBackground('#4F46E5')).toBe('#FFFFFF');
  });

  it('loads, normalizes, deduplicates and bounds recent colors', () => {
    expect(parseRecentColors('["#fff","ffffff","#000000","nope"]')).toEqual(['#FFFFFF', '#000000']);
    expect(parseRecentColors('bad json')).toEqual([]);
    const initial = ['#000000', '#111111', '#222222', '#333333', '#444444', '#555555', '#666666', '#777777'];
    expect(addRecentColor(initial, '#fff')).toEqual(['#FFFFFF', ...initial.slice(0, 7)]);
    expect(addRecentColor(['#FFFFFF', '#000000'], 'fff')).toEqual(['#FFFFFF', '#000000']);
  });
});
