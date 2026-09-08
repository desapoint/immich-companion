import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2SettingsPage from './V2SettingsPage.svelte';

describe('V2SettingsPage', () => {
  it('opens on the live General interface preference', () => {
    const { body } = render(V2SettingsPage);

    expect(body).toContain('Configure interface behavior and live synchronization controls.');
    expect(body).toContain('Interface density');
    expect(body).toContain('Saved locally');
    expect(body).toContain('retained across pages and browser reloads');
    expect(body).toMatch(/aria-selected="true"[^>]*>General<\/button>/);
  });
});
