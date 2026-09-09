import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2ViewerAssetFacts from './V2ViewerAssetFacts.svelte';

describe('V2ViewerAssetFacts', () => {
  it('renders the shared details and metadata structure without associations', () => {
    const { body } = render(V2ViewerAssetFacts, {
      props: {
        filename: 'photo.heic',
        width: 4032,
        height: 3024,
        mimeType: 'image/heic',
        fileSizeBytes: 8_388_608,
        path: '/external/photo.heic',
        takenAt: '2026-08-03T12:00:00Z',
        libraryId: 'library-1',
        delivery: 'decoded',
      },
    });

    expect(body).toContain('Details');
    expect(body).toContain('Metadata');
    expect(body).toContain('8.00 MB');
    expect(body).toContain('External library · library-1');
    expect(body).toContain('decoded browser-compatible derivative');
    expect(body).not.toContain('Relationships');
  });
});
