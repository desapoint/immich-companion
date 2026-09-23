import { expect, test, type Page } from '@playwright/test';

const firstId = '11111111-1111-4111-8111-111111111111';
const secondId = '22222222-2222-4222-8222-222222222222';

const assets = [
  { id: firstId, name: 'comparison-first.jpg', width: 1200, height: 800, color: '#275c4b' },
  { id: secondId, name: 'comparison-second.jpg', width: 1200, height: 800, color: '#7a3f58' },
] as const;

function summary(asset: (typeof assets)[number]) {
  return {
    id: asset.id,
    type: 'IMAGE',
    original_file_name: asset.name,
    original_mime_type: 'image/jpeg',
    width: asset.width,
    height: asset.height,
    duration: null,
    taken_at: '2026-09-20T12:00:00Z',
    file_modified_at: '2026-09-20T12:00:00Z',
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
    source: { kind: 'upload', library_id: null, original_path: `/upload/${asset.name}` },
  };
}

function detail(asset: (typeof assets)[number]) {
  return {
    ...summary(asset),
    owner_id: null,
    library_id: null,
    original_path: `/upload/${asset.name}`,
    created_at: '2026-09-20T12:00:00Z',
    updated_at: '2026-09-20T12:00:00Z',
    exif_info: { fileSizeInByte: 4096 },
  };
}

async function mockComparisonWorkspace(page: Page): Promise<void> {
  await page.route('**/api/assets/search', async (route) => {
    await route.fulfill({ json: { items: assets.map(summary), total: assets.length, page: 1, page_size: 48, pages: 1 } });
  });
  await page.route(/\/api\/assets\/([0-9a-f-]{36})\/summary$/, async (route) => {
    const asset = assets.find((item) => item.id === route.request().url().match(/([0-9a-f-]{36})\/summary$/)?.[1]);
    await route.fulfill({ json: asset ? summary(asset) : null });
  });
  await page.route(/\/api\/assets\/([0-9a-f-]{36})$/, async (route) => {
    const asset = assets.find((item) => item.id === route.request().url().match(/([0-9a-f-]{36})$/)?.[1]);
    await route.fulfill({ json: asset ? detail(asset) : null });
  });
  await page.route('**/api/assets/*/thumbnail?*', async (route) => {
    const asset = assets.find((item) => route.request().url().includes(item.id)) ?? assets[0];
    await route.fulfill({ contentType: 'image/svg+xml', body: `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="${asset.color}"/></svg>` });
  });
  await page.route('**/api/assets/*/original', async (route) => {
    const asset = assets.find((item) => route.request().url().includes(item.id)) ?? assets[0];
    await route.fulfill({ contentType: 'image/svg+xml', body: `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="100%" height="100%" fill="${asset.color}"/></svg>` });
  });
  await page.route('**/api/settings/duplicates/**', async (route) => {
    await route.fulfill({ json: { similarity_threshold: 95, validation_mode: 'strict', max_link_depth: 2, maximum_perceptual_distance: 12, max_candidates: 8 } });
  });
  await page.route('**/api/v2/similarity-debug/compare', async (route) => {
    const pair = {
      asset_id_left: firstId, asset_id_right: secondId, evidence_available: true,
      perceptual_distance: 2, maximum_perceptual_distance: 12, perceptual_gate_pass: true,
      aspect_ratio_difference: 0, maximum_aspect_difference: 0.05, aspect_gate_pass: true,
      candidate_pair_pass: true, neighbor_allocation_simulated: false,
      similarity_percent: 98, structural_percent: 98, perceptual_percent: 98, color_percent: 98,
      normalized_luminance_mae: 0.01, normalized_luminance_rmse: 0.01, normalized_luminance_ssim: 0.99,
      dimensions_equal: true, exact_thumbnail_match: false, detail_changed_percent: 2,
      detail_source: 'preview', similarity_threshold: 95, similarity_threshold_pass: true,
      would_pass_pair_pipeline: true, exclusion_reason: null,
      local_diagnostics: null, model_version: 'test', feature_version: 1, comparison_version: 1,
    };
    await route.fulfill({ json: {
      assets: assets.map((asset) => ({ asset_id: asset.id, evidence_state: 'current', reason: null, width: asset.width, height: asset.height, fingerprint_origin: 'test', model_version: 'test', feature_version: 1, config_fingerprint: 'test' })),
      pairs: [pair], groups: [{ asset_ids: [firstId, secondId], anchor_asset_id: firstId, validation_mode: 'strict', minimum_similarity_percent: 98, maximum_similarity_percent: 98, pair_count: 1, admission_evidence: [] }],
      neighbor_allocation_simulated: false, note: 'Deterministic comparison fixture',
    } });
  });
}

test('adds two viewer assets to Similarity debug and verifies comparison modes', async ({ page }) => {
  await mockComparisonWorkspace(page);
  await page.goto('/assets');
  await page.evaluate(() => localStorage.removeItem('immichCompanionV2SimilarityDebugAssets'));
  await expect(page.getByRole('heading', { level: 1, name: 'Assets' })).toBeVisible();

  const cards = page.locator(`.v2-asset-tile[data-asset-id]`);
  await expect(cards).toHaveCount(2);
  await cards.nth(0).locator('button.v2-asset-main').click();
  const viewer = page.getByRole('dialog', { name: 'Assets Viewer' });
  await viewer.getByRole('button', { name: 'Add to debug' }).click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem('immichCompanionV2SimilarityDebugAssets'))).toContain(firstId);
  await viewer.getByRole('button', { name: 'Next →' }).click();
  await viewer.getByRole('button', { name: 'Add to debug' }).click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem('immichCompanionV2SimilarityDebugAssets'))).toContain(secondId);
  await page.keyboard.press('Escape');

  await page.goto('/similarity-debug');
  await expect(page.getByText('2 of 2 images in this debug group')).toBeVisible();
  await page.getByRole('button', { name: 'Analyze 2 selected' }).click();
  await page.getByRole('button', { name: 'Compare' }).first().click();

  const comparison = page.getByRole('dialog', { name: 'Similarity debug comparison' });
  const modeButtons = ['Side by side', 'Swipe', 'Transparency', 'Difference', 'Local changes', 'Flicker'];
  for (const mode of modeButtons) await expect(comparison.getByRole('button', { name: mode, exact: true })).toBeVisible();

  await comparison.getByRole('button', { name: 'Swipe', exact: true }).click();
  let layers = comparison.locator('.v2-compare-layer');
  await expect(layers).toHaveCount(2);
  const swipeClips = await layers.evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).clipPath));
  expect(swipeClips[0]).toContain('inset');
  expect(swipeClips[1]).toContain('inset');
  expect(swipeClips[0]).not.toBe(swipeClips[1]);

  await comparison.getByRole('button', { name: 'Flicker', exact: true }).click();
  layers = comparison.locator('.v2-compare-layer');
  await expect(layers).toHaveCount(2);
  // Flicker renders selected first and reference second; only one layer is visible at rest.
  await expect(layers.nth(0)).toHaveAttribute('aria-hidden', 'false');
  await expect(layers.nth(1)).toHaveAttribute('aria-hidden', 'true');
  await expect(layers.nth(0)).toHaveCSS('visibility', 'visible');
  await expect(layers.nth(1)).toHaveCSS('visibility', 'hidden');
  const hold = comparison.getByRole('button', { name: 'Hold to show reference' });
  await hold.dispatchEvent('pointerdown', { pointerId: 1, button: 0 });
  await expect(layers.nth(0)).toHaveAttribute('aria-hidden', 'true');
  await expect(layers.nth(1)).toHaveAttribute('aria-hidden', 'false');
  await expect(layers.nth(0)).toHaveCSS('visibility', 'hidden');
  await expect(layers.nth(1)).toHaveCSS('visibility', 'visible');
  await hold.dispatchEvent('pointerup', { pointerId: 1, button: 0 });

  await comparison.getByRole('button', { name: 'Transparency', exact: true }).click();
  layers = comparison.locator('.v2-compare-layer');
  await expect(layers).toHaveCount(2);
  await expect(layers.nth(0)).toHaveAttribute('aria-hidden', 'false');
  await expect(layers.nth(1)).toHaveAttribute('aria-hidden', 'false');

  await page.setViewportSize({ width: 390, height: 844 });
  const selector = comparison.getByRole('combobox', { name: 'Comparison mode' });
  await expect(selector).toBeVisible();
  await selector.selectOption({ label: 'Swipe' });
  await expect(selector).toHaveValue('Swipe');
});
