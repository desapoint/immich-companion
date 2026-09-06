import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import DialogFormActions from './DialogFormActions.svelte';

describe('DialogFormActions', () => {
  it('targets the owning form and switches to its busy label', () => {
    const idle = render(DialogFormActions, {
      props: {
        formId: 'editor',
        submitLabel: 'Create',
        busyLabel: 'Creating…',
        oncancel: () => {},
      },
    }).body;
    const busy = render(DialogFormActions, {
      props: {
        formId: 'editor',
        submitLabel: 'Create',
        busyLabel: 'Creating…',
        busy: true,
        oncancel: () => {},
      },
    }).body;

    expect(idle).toContain('form="editor"');
    expect(idle).toContain('Create');
    expect(busy).toContain('Creating…');
    expect(busy).toContain('disabled');
  });
});
