import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('V2 duplicate linked depth setting', () => {
  it('defaults the user-facing maximum link depth to two', () => {
    expect(source).toContain("maxLinkDepth=$state('2')");
  });

  it('shows the limit only for linked validation with zero-based review semantics', () => {
    expect(source).toContain(`{#if validationMode==='linked'}<V2Field label="Maximum link depth"`);
    expect(source).toContain('0 keeps only direct matches to the group reference.');
    expect(source).toContain('This value matches the link-depth number shown on indirectly linked image pills.');
  });

  it('persists and sends the normalized link depth with discovery', () => {
    expect(source).toContain('maxLinkDepth:normalizedLinkDepth');
    expect(source).toContain('maxLinkDepth=String(saved.maxLinkDepth)');
  });
});
