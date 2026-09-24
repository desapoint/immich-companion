import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('../components/ComparisonRectMask.svelte', import.meta.url), 'utf8');

describe('ComparisonRectMask', () => {
  it('cuts complementary rectangular regions without adding an opaque backing layer', () => {
    expect(source).toContain("? `inset(0 ${100 - split}% 0 0)`");
    expect(source).toContain(": `inset(0 0 0 ${split}%)`");
    expect(source).toContain('style:clip-path={inset}');
    expect(source).not.toContain('background:');
  });
});
