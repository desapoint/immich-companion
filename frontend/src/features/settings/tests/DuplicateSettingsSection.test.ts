import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import DuplicateSettingsSection from '../components/DuplicateSettingsSection.svelte';

describe('DuplicateSettingsSection', () => {
  it('groups source, similarity, and future policy controls by responsibility', () => {
    const { body } = render(DuplicateSettingsSection);

    expect(body).toContain('Duplicate sources');
    expect(body).toContain('Similarity engine');
    expect(body).toContain('Localized comparison alignment');
    expect(body).toContain('Duplicate policy');
    expect(body).toContain('Coming later');
  });
});
