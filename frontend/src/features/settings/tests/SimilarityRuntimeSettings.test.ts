import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import SimilarityRuntimeSettings from '../components/SimilarityRuntimeSettings.svelte';

describe('SimilarityRuntimeSettings', () => {
  it('explains that page sizing is separate from media concurrency', () => {
    const { body } = render(SimilarityRuntimeSettings);

    expect(body).toContain('Similarity fingerprinting');
    expect(body).toContain('does not increase preview fetch or image decode concurrency');
    expect(body).toContain('Loading similarity fingerprint runtime settings');
  });
});
