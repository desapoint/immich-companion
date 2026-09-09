import { describe, expect, it } from 'vitest';

import { isViewerSelectionShortcut, type ViewerSelectionKey } from './viewerSelection';

function key(overrides: Partial<ViewerSelectionKey> = {}): ViewerSelectionKey {
  return { key: ' ', defaultPrevented: false, ctrlKey: false, metaKey: false, altKey: false, ...overrides };
}

describe('viewer selection keyboard shortcut', () => {
  it('matches an unmodified Space press', () => {
    expect(isViewerSelectionShortcut(key())).toBe(true);
  });

  it('does not take Space from an interactive control', () => {
    expect(isViewerSelectionShortcut(key(), true)).toBe(false);
  });

  it('ignores modified, handled, and unrelated keys', () => {
    expect(isViewerSelectionShortcut(key({ ctrlKey: true }))).toBe(false);
    expect(isViewerSelectionShortcut(key({ metaKey: true }))).toBe(false);
    expect(isViewerSelectionShortcut(key({ altKey: true }))).toBe(false);
    expect(isViewerSelectionShortcut(key({ defaultPrevented: true }))).toBe(false);
    expect(isViewerSelectionShortcut(key({ key: 'Enter' }))).toBe(false);
  });
});
