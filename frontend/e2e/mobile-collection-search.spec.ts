import { expect, test } from '@playwright/test';

const mobileViewports = [
  { name: 'small mobile', width: 360, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet mobile', width: 768, height: 1024 },
] as const;

for (const viewport of mobileViewports) {
  test.describe(`${viewport.name} collection search`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test('exposes album search when the context column is hidden', async ({ page }) => {
      await page.goto('/albums');

      const search = page.locator('.v2-mobile-collection-search');
      await expect(search).toBeVisible();
      await expect(search.getByLabel('Search albums')).toBeVisible();
      await expect(search.getByRole('button', { name: 'Search', exact: true })).toBeVisible();
      await expect(page.locator('.v2-context')).toBeHidden();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    });

    test('exposes tag hierarchy search controls when the context column is hidden', async ({ page }) => {
      await page.goto('/tags');

      const search = page.locator('.v2-mobile-collection-search');
      await expect(search).toBeVisible();
      await expect(search.getByLabel('Search tags')).toBeVisible();
      await expect(search.getByRole('switch', { name: 'Match through parent hierarchy' })).toBeVisible();
      await expect(page.locator('.v2-context')).toBeHidden();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    });
  });
}

test.describe('desktop collection search', () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  for (const route of ['/albums', '/tags']) {
    test(`${route} keeps the mobile search duplicate hidden`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator('.v2-mobile-collection-search')).toBeHidden();
      await expect(page.locator('.v2-context')).toBeVisible();
    });
  }
});
