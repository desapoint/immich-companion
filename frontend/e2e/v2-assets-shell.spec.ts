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
