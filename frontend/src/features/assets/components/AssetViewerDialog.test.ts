import { describe, expect, it } from 'vitest';

import { shouldHandleViewerShortcut } from './AssetViewerDialog.svelte';

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
