import { readFileSync } from 'node:fs';

import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import SimilarityEvidenceGenerationPanel from '../components/SimilarityEvidenceGenerationPanel.svelte';

const source = readFileSync(
  new URL('../components/SimilarityEvidenceGenerationPanel.svelte', import.meta.url),
  'utf8',
);

describe('SimilarityEvidenceGenerationPanel', () => {
  it('exposes separate destroy-only and immediate-rebuild controls', () => {
    const { body } = render(SimilarityEvidenceGenerationPanel);

    expect(body).toContain('Similarity evidence generation');
    expect(body).toContain('Destroy evidence only');
    expect(body).toContain('Start new evidence epoch &amp; rebuild');
    expect(body).toContain('hard boundary for search fingerprints');
    expect(body).toContain('Destroy only leaves the evidence empty until a later similarity scan.');
    expect(body).toContain('Review decisions and resolution history are preserved.');
    expect(body).toContain('Refresh epoch status');
  });

  it('rebuilds with every saved membership-affecting discovery setting', () => {
    expect(source).toContain('similarity_threshold:preferences.similarityThreshold');
    expect(source).toContain('validation_mode:preferences.validationMode');
    expect(source).toContain('max_link_depth:preferences.maxLinkDepth');
    expect(source).toContain(
      'maximum_neighbors_per_asset:Math.min(64,Math.max(1,preferences.maxCandidates))',
    );
    expect(source).toContain('threshold, validation mode, link depth, and candidate limit');
  });
});
