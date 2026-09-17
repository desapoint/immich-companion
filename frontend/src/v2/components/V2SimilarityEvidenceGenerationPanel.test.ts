import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2SimilarityEvidenceGenerationPanel from './V2SimilarityEvidenceGenerationPanel.svelte';

describe('V2SimilarityEvidenceGenerationPanel', () => {
  it('always exposes the destructive epoch rebuild control independently of cache telemetry', () => {
    const { body } = render(V2SimilarityEvidenceGenerationPanel);

    expect(body).toContain('Similarity evidence generation');
    expect(body).toContain('Start new evidence epoch &amp; rebuild');
    expect(body).toContain('hard boundary for search fingerprints');
    expect(body).toContain('Review decisions and resolution history are preserved.');
    expect(body).toContain('Refresh epoch status');
  });
});
