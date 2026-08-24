import { expect, test, type Page } from '@playwright/test';

const useLiveApi = process.env.PLAYWRIGHT_USE_LIVE_API === '1';

const assets = [
  {
    id: '11111111-1111-4111-8111-111111111111',
    type: 'IMAGE',
    original_file_name: 'first-image.jpg',
    original_mime_type: 'image/jpeg',
    width: 2048,
    height: 1365,
    duration: null,
    taken_at: '2026-08-20T12:00:00Z',
    file_modified_at: '2026-08-20T12:00:00Z',
    is_favorite: true,
    is_archived: false,
    is_trashed: false,
    is_offline: false,
    is_edited: false,
    visibility: 'timeline',
    has_metadata: true,
    live_photo_video_id: null,
    file_size_bytes: 4096,
    people_count: 1,
    tag_count: 1,
    stack_count: 0,
  },
  {
    id: '22222222-2222-4222-8222-222222222222',
    type: 'IMAGE',
    original_file_name: 'second-image.jpg',
    original_mime_type: 'image/jpeg',
    width: 1600,
    height: 1200,
    duration: null,
    taken_at: '2026-08-19T12:00:00Z',
    file_modified_at: '2026-08-19T12:00:00Z',
    is_favorite: false,
    is_archived: false,
    is_trashed: false,
    is_offline: false,
    is_edited: true,
    visibility: 'timeline',
    has_metadata: true,
    live_photo_video_id: null,
    file_size_bytes: 8192,
    people_count: 0,
    tag_count: 0,
    stack_count: 0,
  },
];

async function mockAssetWorkspace(page: Page): Promise<void> {
  await page.route('**/api/assets/sync', async (route) => {
    await route.fulfill({ json: { seen: 2, created: 0, updated: 2, removed: 0, completed_at: new Date().toISOString() } });
  });
  await page.route('**/api/assets/search', async (route) => {
    await route.fulfill({ json: { items: assets, total: 2, page: 1, page_size: 48, pages: 1 } });
  });
  await page.route('**/api/albums', async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/assets/*', async (route) => {
    const assetId = route.request().url().split('/').at(-1) ?? assets[0].id;
    const asset = assets.find((item) => item.id === assetId) ?? assets[0];
    await route.fulfill({
      json: {
        id: asset.id,
        owner_id: null,
        library_id: null,
        type: asset.type,
        original_file_name: asset.original_file_name,
        original_path: `/upload/${asset.original_file_name}`,
        original_mime_type: asset.original_mime_type,
        width: asset.width,
        height: asset.height,
        duration: null,
        taken_at: asset.taken_at,
        file_modified_at: asset.file_modified_at,
        created_at: asset.taken_at,
        updated_at: asset.file_modified_at,
        is_favorite: asset.is_favorite,
        is_archived: false,
        is_trashed: false,
        is_offline: false,
        is_edited: asset.is_edited,
        visibility: 'timeline',
        live_photo_video_id: null,
        exif_info: { make: 'Companion Test Camera', fileSizeInByte: asset.file_size_bytes },
        people: [],
        tags: [],
        stack: null,
        immich_url: `https://photos.example.test/photos/${asset.id}`,
      },
    });
  });
  await page.route('**/api/assets/*/thumbnail?*', async (route) => {
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220"><rect width="100%" height="100%" fill="#275c4b"/></svg>',
    });
  });
  await page.route('**/api/assets/*/original', async (route) => {
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="1365"><rect width="100%" height="100%" fill="#4f8f78"/></svg>',
    });
  });
}

test('searches cards and operates the fullscreen asset viewer', async ({ page }) => {
  if (useLiveApi) {
    const sync = await page.request.post('/api/assets/sync');
    expect(sync.ok()).toBe(true);
  } else {
    await mockAssetWorkspace(page);
  }

  await page.goto('/assets');

  await expect(page.getByRole('heading', { level: 1, name: 'Search Immich assets' })).toBeVisible();
  const cards = page.locator('article.asset-card');
  await expect(cards.first()).toBeVisible();
  await expect(cards).toHaveCount(useLiveApi ? 48 : 2);

  await cards.first().getByRole('button', { name: /Open .* in viewer/ }).click();
  const viewer = page.getByRole('dialog', { name: /.+/ });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByText(/1 of \d+ images/)).toBeVisible();

  await viewer.getByRole('button', { name: 'Select image' }).click();
  await expect(viewer.getByRole('button', { name: '✓ Selected' })).toBeVisible();

  await viewer.getByRole('button', { name: 'Actual size' }).click();
  await expect(viewer.getByRole('button', { name: 'Fit to screen' })).toBeVisible();

  await viewer.getByRole('button', { name: 'Zoom in' }).click();
  await expect(viewer.getByTitle('Reset zoom (0)')).toContainText('120%');

  await viewer.getByRole('button', { name: 'Keyboard' }).click();
  await expect(viewer.getByText('Keyboard shortcuts')).toBeVisible();

  await viewer.getByRole('button', { name: 'More info' }).click();
  await expect(viewer.getByText('Immich metadata')).toBeVisible();

  await page.keyboard.press('ArrowRight');
  await expect(viewer.getByText(/2 of \d+ images/)).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(viewer).toBeHidden();
});
