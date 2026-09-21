import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('V2DuplicatesPage evidence controls', () => {
  it('mounts evidence generation only in Rules & discovery', () => {
    expect(source).toContain("{#if tab==='Rules & discovery'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
    expect(source).not.toContain("{#if tab!=='Resolution history'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
  });

  it('keeps the review confirmation mounted until reconciliation finishes', () => {
    const confirmation = source.indexOf('await operations.waitForReconciliation();pendingReview=null');
    const apply = source.indexOf('await applyGroupDecisionSet(review.groupId,review.plan)');
    expect(confirmation).toBeGreaterThan(apply);
    expect(source).toContain("pendingLabel={operations.phase==='reconciling'?'Refreshing results…':'Applying actions…'}");
  });
});
