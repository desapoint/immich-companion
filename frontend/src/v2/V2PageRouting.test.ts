import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('V2 page composition', () => {
  it('routes the live restore page instead of the implementation placeholder', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/v2/V2Page.svelte'), 'utf8');
    expect(source).toContain("activeKey === 'restore'");
    expect(source).toContain('<V2RestorePage selectionController={restoreSelection} />');
  });

  it('routes the static playground instead of the implementation placeholder', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/v2/V2Page.svelte'), 'utf8');
    expect(source).toContain("activeKey === 'playground'");
    expect(source).toContain('<V2PlaygroundPage />');
  });
});
