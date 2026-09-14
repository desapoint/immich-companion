import { describe, expect, it } from 'vitest';

import { SelectionOwnership } from './selectionOwnership';

describe('SelectionOwnership', () => {
  it('invalidates an operation owner after the selection changes', () => {
    const ownership = new SelectionOwnership('page-a');
    const owner = ownership.current();

    expect(ownership.owns(owner)).toBe(true);
    ownership.changed();
    expect(ownership.owns(owner)).toBe(false);
    expect(ownership.owns(ownership.current())).toBe(true);
  });

  it('does not let a recovered task own a selection from another page session', () => {
    const previousPage = new SelectionOwnership('page-a');
    const recoveredOwner = previousPage.current();
    const reloadedPage = new SelectionOwnership('page-b');

    expect(reloadedPage.owns(recoveredOwner)).toBe(false);
  });
});
