import { expect, test } from '@playwright/test';

const tabletViewports = [
  { name: 'compact tablet', width: 700, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'wide tablet', width: 880, height: 900 },
] as const;

const routes = ['/assets', '/albums', '/tags', '/docs', '/playground', '/duplicates'] as const;

for (const viewport of tabletViewports) {
  test.describe(`${viewport.name} scrolling`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    for (const route of routes) {
      test(`${route} keeps the content pane scrollable`, async ({ page }) => {
        await page.goto(route);
        const content = page.locator('.v2-content');
        await expect(content).toBeVisible();

        if (route === '/albums' || route === '/tags') {
          const table = content.locator('.v2-table').first();
          await expect(table).toBeVisible();
          await expect.poll(() => table.evaluate((element) => getComputedStyle(element).display)).toBe('block');
          const tableWidth = await table.evaluate((element) => ({
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
          }));
          expect(tableWidth.scrollWidth).toBeLessThanOrEqual(tableWidth.clientWidth);
        }

        if (route === '/duplicates') {
          await expect.poll(() => page.locator('.v2-page-host[data-page-title="Duplicates"] .v2-head-row')
            .evaluate((element) => getComputedStyle(element).flexDirection)).toBe('column');
          await expect(page.locator('.v2-page-host[data-page-title="Duplicates"] .v2-page-title')).toBeVisible();
        }

        // Keep this geometry check deterministic when the seeded API has no
        // rows for a particular collection. It still exercises the real shell
        // scroll contract and never changes the application source DOM.
        await content.evaluate((element) => {
          const sentinel = document.createElement('div');
          sentinel.dataset.tabletScrollSentinel = 'true';
          sentinel.style.height = '1800px';
          sentinel.style.pointerEvents = 'none';
          element.append(sentinel);
        });

        const geometry = await content.evaluate((element) => ({
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        }));
        expect(geometry.clientHeight).toBeGreaterThan(0);
        expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight);
        expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);

        await content.evaluate((element) => element.scrollTo({ top: element.scrollHeight, behavior: 'instant' }));
        await expect.poll(() => content.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
        await expect.poll(() => content.evaluate((element) => element.scrollTop + element.clientHeight))
          .toBeGreaterThanOrEqual(geometry.scrollHeight - 1);

        const sidebar = page.locator('.v2-sidebar');
        await expect(sidebar).toBeVisible();
        const sidebarBefore = await sidebar.boundingBox();
        await content.evaluate((element) => element.scrollTo({ top: 0, behavior: 'instant' }));
        const sidebarAfter = await sidebar.boundingBox();
        expect(sidebarBefore).not.toBeNull();
        expect(sidebarAfter).not.toBeNull();
        expect(sidebarAfter!.y).toBe(sidebarBefore!.y);
      });
    }
  });
}
