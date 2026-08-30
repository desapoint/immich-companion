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
    expect(body).toContain('Most recently uploaded');
    expect(body).not.toContain('<select');
  });
});
