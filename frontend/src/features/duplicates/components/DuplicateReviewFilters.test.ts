import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateReviewFilter } from '../state/duplicateReviewFilters';
import DuplicateReviewFilters from './DuplicateReviewFilters.svelte';

describe('DuplicateReviewFilters', () => {
  it('renders every workflow category with its count and active state', () => {
    const counts = Object.fromEntries([
      'all',
      'auto_ready',
      'resolve_ready',
      'stack_ready',
      'needs_review',
      'analyzing',
      'integrity_warning',
      'immich_duplicates',
    ].map((key, index) => [key, index])) as Record<DuplicateReviewFilter, number>;
    const body = render(DuplicateReviewFilters, {
      props: {
        active: 'needs_review',
        counts,
        onchange: () => undefined,
      },
    }).body;

    expect(body).toContain('aria-label="Filter duplicate groups"');
    expect(body).toContain('Auto ready');
    expect(body).toContain('Integrity warning');
    expect(body).toContain('Immich duplicates');
    expect(body).toMatch(/aria-pressed="true"[^>]*>\s*<span>Needs review<\/span>/);
  });
});
