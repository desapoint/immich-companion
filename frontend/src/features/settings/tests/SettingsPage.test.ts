import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import SettingsPage from '../components/SettingsPage.svelte';

describe('SettingsPage', () => {
  it('opens on the live General interface preference', () => {
    const { body } = render(SettingsPage);

    expect(body).toContain('Configure interface behavior and live synchronization controls.');
    expect(body).toContain('Interface density');
    expect(body).toContain('Saved locally');
    expect(body).toContain('retained across pages and browser reloads');
    expect(body).toContain('Action notifications');
    expect(body).toContain('Toast position');
    expect(body).toContain('Open playground');
    expect(body).toContain('Tasks');
    expect(body).toContain('Interface preferences and local tools.');
    expect(body).toMatch(/aria-selected="true"[^>]*>General<\/button>/);
  });
});
