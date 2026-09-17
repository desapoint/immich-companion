import { expect, test, type Page } from '@playwright/test';

async function mockEmptyAssetWorkspace(page: Page): Promise<void> {
  const emptyPage = { items: [], total: 0, page: 1, page_size: 24, pages: 1 };
  await page.route('**/api/assets/search', async (route) => {
    await route.fulfill({ json: emptyPage });
  });
  await page.route('**/api/albums/manage?*', async (route) => {
    await route.fulfill({ json: emptyPage });
  });
  await page.route('**/api/tags/manage?*', async (route) => {
    await route.fulfill({ json: emptyPage });
  });
}

async function mockViewerAssetWorkspace(page: Page): Promise<void> {
  const id = '11111111-1111-4111-8111-111111111111';
  const summary = {
    id,
    type: 'IMAGE',
    original_file_name: 'viewer-regression.jpg',
    original_mime_type: 'image/jpeg',
    width: 1200,
    height: 800,
    duration: null,
    taken_at: '2026-09-17T12:00:00Z',
    file_modified_at: '2026-09-17T12:00:00Z',
    is_favorite: false,
    is_archived: false,
    is_trashed: false,
    is_offline: false,
    is_edited: false,
    visibility: 'timeline',
    has_metadata: true,
    live_photo_video_id: null,
    file_size_bytes: 4096,
    tags: [],
    albums: [],
    stack: null,
    source: { kind: 'upload', library_id: null, original_path: '/upload/viewer-regression.jpg' },
  };
  const emptyPage = { items: [], total: 0, page: 1, page_size: 24, pages: 1 };

  await page.route('**/api/assets/search', async (route) => {
    await route.fulfill({ json: { items: [summary], total: 1, page: 1, page_size: 24, pages: 1 } });
  });
  await page.route('**/api/albums/manage?*', async (route) => {
    await route.fulfill({ json: emptyPage });
  });
  await page.route('**/api/tags/manage?*', async (route) => {
    await route.fulfill({ json: emptyPage });
  });
  await page.route(`**/api/assets/${id}/summary`, async (route) => {
    await route.fulfill({ json: summary });
  });
  await page.route(new RegExp(`/api/assets/${id}$`), async (route) => {
    await route.fulfill({
      json: {
        id,
        owner_id: null,
        library_id: null,
        type: 'IMAGE',
        original_file_name: 'viewer-regression.jpg',
        original_path: '/upload/viewer-regression.jpg',
        original_mime_type: 'image/jpeg',
        width: 1200,
        height: 800,
        duration: null,
        taken_at: '2026-09-17T12:00:00Z',
        file_modified_at: '2026-09-17T12:00:00Z',
        created_at: '2026-09-17T12:00:00Z',
        updated_at: '2026-09-17T12:00:00Z',
        is_favorite: false,
        is_archived: false,
        is_trashed: false,
        is_offline: false,
        is_edited: false,
        visibility: 'timeline',
        live_photo_video_id: null,
        exif_info: { fileSizeInByte: 4096 },
        tags: [],
        stack: null,
      },
    });
  });
  await page.route(`**/api/assets/${id}/thumbnail?*`, async (route) => {
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="#365a72"/></svg>',
    });
  });
  await page.route(`**/api/assets/${id}/original`, async (route) => {
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="#557e99"/></svg>',
    });
  });
}

test('routes the implemented live Assets workspace from the V2 shell', async ({ page }) => {
  await mockEmptyAssetWorkspace(page);
  await page.goto('/v2/assets');

  await expect(page.getByRole('heading', { level: 1, name: 'Assets' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Search assets' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Browse' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('0 matches', { exact: true })).toBeVisible();
  await expect(page.getByText('Simple search · No filters', { exact: true })).toHaveCount(0);
  await expect(page.getByText(/remains intentionally non-live in V2/)).toHaveCount(0);
});

test('opens the V2 asset viewer without a recursive Svelte effect failure', async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on('pageerror', (error) => runtimeErrors.push(error.message));

  await mockViewerAssetWorkspace(page);
  await page.goto('/v2/assets');

  await page.getByRole('button', { name: 'Preview viewer-regression.jpg' }).click();
  const viewer = page.getByRole('dialog', { name: 'Assets Viewer' });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole('region', { name: 'Image viewport' })).toBeVisible();
  await expect(page.getByText('FRONTEND INTERRUPTED')).toHaveCount(0);

  await page.waitForTimeout(100);
  expect(runtimeErrors.join('\n')).not.toContain('effect_update_depth_exceeded');
});
