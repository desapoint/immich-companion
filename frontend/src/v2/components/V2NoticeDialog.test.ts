import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2NoticeDialog from './V2NoticeDialog.svelte';

describe('V2NoticeDialog', () => {
  it('renders an accessible informational dialog with a close action', () => {
    const { body } = render(V2NoticeDialog, {
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
