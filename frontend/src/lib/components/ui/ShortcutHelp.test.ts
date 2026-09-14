import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import ShortcutHelp from './ShortcutHelp.svelte';

describe('ShortcutHelp', () => {
  const items = [
    { shortcut: '← / H', description: 'Previous image' },
    { shortcut: '→ / L', description: 'Next image' },
  ];

  it('renders an accessible pin control from data', () => {
    const { body } = render(ShortcutHelp, { props: { items } });
    expect(body).toContain('Pin keyboard shortcuts');
    expect(body).toContain('aria-expanded="false"');
    expect(body).toContain('aria-pressed="false"');
  });

  it('renders supplied shortcut descriptions when pinned open', () => {
    const { body } = render(ShortcutHelp, { props: { items, open: true } });
    expect(body).toContain('Unpin keyboard shortcuts');
    expect(body).toContain('aria-expanded="true"');
    expect(body).toContain('aria-pressed="true"');
    expect(body).toContain('Previous image');
    expect(body).toContain('Next image');
    expect(body).toContain('← / H');
  });
});
