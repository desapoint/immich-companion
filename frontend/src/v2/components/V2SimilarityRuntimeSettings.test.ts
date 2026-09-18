import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2SimilarityRuntimeSettings from './V2SimilarityRuntimeSettings.svelte';

describe('V2SimilarityRuntimeSettings', () => {
  it('explains that page sizing is separate from media concurrency', () => {
    const { body } = render(V2SimilarityRuntimeSettings);

    expect(body).toContain('Similarity fingerprinting');
    expect(body).toContain('does not increase preview fetch or image decode concurrency');
    expect(body).toContain('Loading similarity fingerprint runtime settings');
  });
});
