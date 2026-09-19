import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('./V2DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('V2DuplicatesPage evidence controls', () => {
  it('mounts evidence generation only in Rules & discovery', () => {
    expect(source).toContain("{#if tab==='Rules & discovery'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
    expect(source).not.toContain("{#if tab!=='Resolution history'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
  });
});
