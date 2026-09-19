import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import CronField from './CronField.svelte';

describe('CronField', () => {
  it('shows a real last-run field separately from the computed next run', () => {
    const { body } = render(CronField, {
      props: {
        id: 'sync-cron',
        value: '0 * * * *',
        enabled: true,
        lastRunAt: null,
      },
    });

    expect(body).toContain('Next run');
    expect(body).toContain('Last ran');
    expect(body).toContain('Never');
  });
});
