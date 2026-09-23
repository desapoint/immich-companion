import { expect, test, type Page } from '@playwright/test';

const assetId = '22222222-2222-4222-8222-222222222222';

function assetSummary(trashed = false) {
  return {
    id: assetId,
    type: 'IMAGE',
    original_file_name: trashed ? 'mobile-trash.jpg' : 'mobile-viewer.jpg',
    original_mime_type: 'image/jpeg',
    width: 1200,
    height: 800,
    duration: null,
    taken_at: '2026-09-18T12:00:00Z',
    file_modified_at: '2026-09-18T12:00:00Z',
    is_favorite: false,
    is_archived: false,
    is_trashed: trashed,
    is_offline: false,
    is_edited: false,
    visibility: 'timeline',
    has_metadata: true,
    live_photo_video_id: null,
    file_size_bytes: 4096,
    tags: [],
    albums: [],
    stack: null,
    source: { kind: 'upload', library_id: null, original_path: '/upload/mobile.jpg' },
    restore_path: '/upload/mobile.jpg',
  };
}

async function mockMedia(page: Page, trashed = false): Promise<void> {
  const summary = assetSummary(trashed);
  const empty = { items: [], total: 0, page: 1, page_size: 24, pages: 1 };
  await page.route('**/api/albums/manage?*', (route) => route.fulfill({ json: empty }));
  await page.route('**/api/tags/manage?*', (route) => route.fulfill({ json: empty }));
  await page.route('**/api/assets/search', (route) => route.fulfill({ json: {
    items: trashed ? [] : [summary], total: trashed ? 0 : 1, page: 1, page_size: 24, pages: 1,
  } }));
  await page.route(`**/api/restore?*`, (route) => route.fulfill({ json: {
    items: trashed ? [summary] : [], total: trashed ? 1 : 0, page: 1, page_size: 24, pages: 1,
  } }));
  await page.route(`**/api/assets/${assetId}/summary`, (route) => route.fulfill({ json: summary }));
  await page.route(new RegExp(`/api/assets/${assetId}$`), (route) => route.fulfill({ json: {
    ...summary, owner_id: null, library_id: null, original_path: '/upload/mobile.jpg',
    created_at: '2026-09-18T12:00:00Z', updated_at: '2026-09-18T12:00:00Z', exif_info: { fileSizeInByte: 4096 },
  } }));
  await page.route(`**/api/restore/${assetId}`, (route) => route.fulfill({ json: {
    ...summary, owner_id: null, library_id: null, original_path: '/upload/mobile.jpg',
    created_at: '2026-09-18T12:00:00Z', updated_at: '2026-09-18T12:00:00Z', exif_info: { fileSizeInByte: 4096 },
  } }));
  await page.route(`**/api/assets/${assetId}/thumbnail?*`, (route) => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="#365a72"/></svg>',
  }));
  await page.route(`**/api/assets/${assetId}/original`, (route) => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="#557e99"/></svg>',
  }));
}

async function assertMobileViewport(page: Page): Promise<void> {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

for (const viewport of [{ width: 390, height: 844 }, { width: 360, height: 740 }]) {
  test(`keeps the asset viewer usable at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockMedia(page);
    await page.goto('/assets');
    await page.locator('.v2-asset-main').filter({ hasText: 'mobile-viewer.jpg' }).click();

    const viewer = page.getByRole('dialog', { name: 'Assets Viewer' });
    await expect(viewer).toBeVisible();
    await expect(viewer.getByRole('region', { name: 'Image viewport' })).toBeVisible();
    await assertMobileViewport(page);

    const stage = viewer.locator('.v2-viewer-stage');
    await stage.evaluate((node) => node.scrollTo({ top: node.scrollHeight, behavior: 'instant' }));
    await expect(viewer.getByText('Relationships')).toBeVisible();
    await expect(viewer.getByRole('button', { name: 'Trash' })).toBeVisible();
    await assertMobileViewport(page);
  });
}

test('keeps the trash viewer info and controls reachable on a tablet', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await mockMedia(page, true);
  await page.goto('/restore');
  await page.locator('.v2-asset-main').filter({ hasText: 'mobile-trash.jpg' }).click();

  const viewer = page.getByRole('dialog', { name: 'Trash Viewer' });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole('region', { name: 'Image viewport' })).toBeVisible();
  await expect(viewer.getByText('Restore boundary')).toBeVisible();
  await expect(viewer.getByRole('button', { name: 'Restore visible' })).toBeVisible();
  await assertMobileViewport(page);
});
