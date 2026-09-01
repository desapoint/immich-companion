import { describe, expect, it } from 'vitest';

import { duplicateViewerShortcut, shouldHandleViewerShortcut } from './AssetViewerDialog.svelte';

interface TargetStub {
  closest: (selector: string) => object | null;
}

function targetStub(closestDialog: object | null, closestControl: object | null): TargetStub {
  return {
    closest: (selector) => selector.startsWith('dialog') || selector.includes('[role="dialog"]')
      ? closestDialog
      : closestControl,
  };
}

describe('AssetViewerDialog keyboard shortcuts', () => {
  it('maps duplicate review shortcuts without affecting unrelated keys', () => {
    expect(duplicateViewerShortcut('k')).toBe('keep');
    expect(duplicateViewerShortcut('d')).toBe('delete');
    expect(duplicateViewerShortcut('s')).toBe('stack');
    expect(duplicateViewerShortcut('p')).toBe('primary');
    expect(duplicateViewerShortcut('i')).toBeNull();
  });

  it('allows shortcuts from the viewer surface', () => {
    const viewer = {};
    expect(shouldHandleViewerShortcut(targetStub(viewer, null), viewer)).toBe(true);
  });

  it('does not capture keys from nested dialogs', () => {
    const viewer = {};
    expect(shouldHandleViewerShortcut(targetStub({}, null), viewer)).toBe(false);
  });

  it('does not capture keys from buttons or editable controls', () => {
    const viewer = {};
    expect(shouldHandleViewerShortcut(targetStub(viewer, {}), viewer)).toBe(false);
  });
});
