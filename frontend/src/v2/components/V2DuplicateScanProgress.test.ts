import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2DuplicateScanProgress from './V2DuplicateScanProgress.svelte';

describe('V2DuplicateScanProgress', () => {
  it('shows determinate task counters without replacing prior results', () => {
    const { body } = render(V2DuplicateScanProgress, {
      props: {
        progress: {
          phase: 'Comparing candidate pairs',
          completed: 125,
          total: 500,
          percent: 35,
          detail: 'Scored 125 of 500 candidate pairs',
          candidatePairs: 500,
          matchesFound: 8,
        },
      },
    });

    expect(body).toContain('Comparing candidate pairs');
    expect(body).toContain('125 / 500');
    expect(body).toContain('500 candidate pairs');
    expect(body).toContain('8 matches retained');
    expect(body).toContain('aria-valuenow="35"');
    expect(body).toContain('previous completed results remain visible');
  });

  it('uses indeterminate progress while exact-file preparation has no total', () => {
    const { body } = render(V2DuplicateScanProgress, {
      props: {
        progress: {
          phase: 'Verifying exact-file candidates',
          completed: 0,
          total: null,
          percent: null,
          detail: 'Waiting for the background worker…',
          candidatePairs: null,
          matchesFound: null,
        },
      },
    });

    expect(body).toContain('data-indeterminate="true"');
    expect(body).not.toContain('aria-valuenow');
  });
});
