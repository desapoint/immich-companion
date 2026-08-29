import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetViewerHeader from './AssetViewerHeader.svelte';

describe('AssetViewerHeader', () => {
  it('offers Restore-specific selection and direct restore without normal asset actions', () => {
    const { body } = render(AssetViewerHeader, {
      props: {
        filename: 'trashed.jpg',
        selectedFilename: 'trashed.jpg',
        selected: false,
        scaleMode: 'fit',
        infoOpen: false,
        helpOpen: false,
        zoomPercent: 100,
        actionSummary: null,
        albums: [],
        tags: [],
        actionsEnabled: false,
        selectionEnabled: true,
        onrestore: () => undefined,
        onaction: () => undefined,
        onrelationconfirm: () => undefined,
        ontoggleselection: () => undefined,
        ontogglescale: () => undefined,
        onzoomout: () => undefined,
        onzoomreset: () => undefined,
        onzoomin: () => undefined,
        ontoggleinfo: () => undefined,
        ontogglehelp: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Restore image"');
    expect(body).toContain('aria-label="Select image"');
    expect(body).not.toContain('aria-label="Favorite selected image"');
    expect(body).not.toContain('aria-label="Delete selected image (move to trash)"');
  });

  it('shows the selected and busy states', () => {
    const { body } = render(AssetViewerHeader, {
      props: {
        filename: 'trashed.jpg',
        selectedFilename: 'trashed.jpg',
        selected: true,
        scaleMode: 'fit',
        infoOpen: false,
        helpOpen: false,
        zoomPercent: 100,
        actionSummary: null,
        albums: [],
        tags: [],
        actionsEnabled: false,
        selectionEnabled: true,
        restoreBusy: true,
        onrestore: () => undefined,
        onaction: () => undefined,
        onrelationconfirm: () => undefined,
        ontoggleselection: () => undefined,
        ontogglescale: () => undefined,
        onzoomout: () => undefined,
        onzoomreset: () => undefined,
        onzoomin: () => undefined,
        ontoggleinfo: () => undefined,
        ontogglehelp: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Restoring image…"');
    expect(body).toContain('aria-label="Deselect image"');
    expect(body).toContain('disabled');
  });

  it('keeps a direct integrity action in the normal viewer header', () => {
    const { body } = render(AssetViewerHeader, {
      props: {
        filename: 'active.jpg',
        selectedFilename: 'active.jpg',
        selected: false,
        scaleMode: 'fit',
        infoOpen: false,
        helpOpen: false,
        zoomPercent: 100,
        actionSummary: null,
        albums: [],
        tags: [],
        actionsEnabled: false,
        selectionEnabled: false,
        onintegrity: () => undefined,
        onaction: () => undefined,
        onrelationconfirm: () => undefined,
        ontoggleselection: () => undefined,
        ontogglescale: () => undefined,
        onzoomout: () => undefined,
        onzoomreset: () => undefined,
        onzoomin: () => undefined,
        ontoggleinfo: () => undefined,
        ontogglehelp: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Analyze file integrity"');
  });
});
