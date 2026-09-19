import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import NoticeDialog from './NoticeDialog.svelte';

describe('NoticeDialog', () => {
  it('renders an accessible informational dialog with a close action', () => {
    const { body } = render(NoticeDialog, {
      props: {
        id: 'not-implemented',
        title: 'Not implemented',
        message: 'This feature is not available yet.',
        onclose: () => undefined,
      },
    });

    expect(body).toContain('role="dialog"');
    expect(body).toContain('Not implemented');
    expect(body).toContain('This feature is not available yet.');
    expect(body).toContain('data-variant="primary"');
    expect(body).toMatch(/>\s*(?:<!---->)?Close/);
  });
});
