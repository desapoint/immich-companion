import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import ShortcutHelp from './ShortcutHelp.svelte';

describe('ShortcutHelp', () => {
  const items = [
    { shortcut: '← / H', description: 'Previous image' },
    { shortcut: '→ / L', description: 'Next image' },
  ];

  it('renders an accessible shortcut button from data', () => {
    const { body } = render(ShortcutHelp, { props: { items } });
    expect(body).toContain('Show keyboard shortcuts');
    expect(body).toContain('aria-expanded="false"');
  });

  it('renders supplied shortcut descriptions when pinned open', () => {
    const { body } = render(ShortcutHelp, { props: { items, open: true } });
    expect(body).toContain('aria-expanded="true"');
    expect(body).toContain('Previous image');
    expect(body).toContain('Next image');
    expect(body).toContain('← / H');
  });
});
