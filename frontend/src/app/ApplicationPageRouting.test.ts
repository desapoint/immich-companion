import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('application page composition', () => {
  it('is the primary page composition without a legacy branch', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/app/ApplicationPage.svelte'), 'utf8');
    expect(source).not.toContain('V2Page.svelte');
    expect(source).not.toContain('V2Shell.svelte');
  });

  it('routes the live restore page instead of the implementation placeholder', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/app/ApplicationPage.svelte'), 'utf8');
    expect(source).toContain("activeKey === 'restore'");
    expect(source).toContain('<V2RestorePage selectionController={restoreSelection} />');
  });

  it('routes the live duplicates page instead of the implementation placeholder', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/app/ApplicationPage.svelte'), 'utf8');
    expect(source).toContain("activeKey === 'duplicates'");
    expect(source).toContain('<DuplicatesPage />');
  });

  it('routes the static playground instead of the implementation placeholder', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/app/ApplicationPage.svelte'), 'utf8');
    expect(source).toContain("activeKey === 'playground'");
    expect(source).toContain('<PlaygroundPage />');
  });
});
