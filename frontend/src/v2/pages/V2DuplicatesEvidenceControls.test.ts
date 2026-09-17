import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('./V2DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('V2DuplicatesPage evidence controls', () => {
  it('mounts evidence generation outside the Rules & discovery-only main-content branch', () => {
    const evidencePanel = source.indexOf("{#if tab!=='Resolution history'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
    const reviewBranch = source.indexOf("{#if tab==='Review'}<V2Toolbar>");
    const rulesBranch = source.indexOf("{:else if tab==='Rules & discovery'}<V2Toolbar");

    expect(evidencePanel).toBeGreaterThan(-1);
    expect(evidencePanel).toBeLessThan(reviewBranch);
    expect(evidencePanel).toBeLessThan(rulesBranch);
  });
});
