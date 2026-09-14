import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import StatusNotice from './StatusNotice.svelte';

describe('StatusNotice', () => {
  it('renders error notices as alerts with an optional action', () => {
    const { body } = render(StatusNotice, {
      props: {
        tone: 'error',
        message: 'Could not refresh.',
        actionLabel: 'Retry',
        onaction: () => {},
      },
    });

    expect(body).toContain('role="alert"');
    expect(body).toContain('Could not refresh.');
    expect(body).toContain('Retry');
  });

  it('renders success notices as polite status updates', () => {
    const { body } = render(StatusNotice, {
      props: { tone: 'success', message: 'Saved.' },
    });

    expect(body).toContain('role="status"');
    expect(body).toContain('aria-live="polite"');
    expect(body).toContain('Saved.');
  });
});
