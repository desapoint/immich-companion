import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import DuplicatesPage from './DuplicatesPage.svelte';

describe('DuplicatesPage', () => {
  it('uses the shared custom selector for the keeper rule', () => {
    const { body } = render(DuplicatesPage, {
      props: { onpreview: () => undefined },
    });

    expect(body).toContain('id="duplicate-keeper-policy"');
    expect(body).toContain('aria-haspopup="listbox"');
    expect(body).toContain('Prefer uploads');
    expect(body).toContain('id="duplicate-exact-policy"');
    expect(body).toContain('id="duplicate-library-filter"');
    expect(body).not.toContain('<select');
    expect(body).toContain('Verify upload streams too');
    expect(body).toContain('Apply automatic rules');
  });
});
