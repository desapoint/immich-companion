import { expect, test } from '@playwright/test';

const phoneViewports = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'small mobile', width: 360, height: 800 },
] as const;

const routes = ['/albums', '/tags', '/docs', '/similarity-debug'] as const;

for (const viewport of phoneViewports) {
  test.describe(`${viewport.name} fixed navigation clearance`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    for (const route of routes) {
      test(`${route} reaches its final controls above the fixed nav`, async ({ page }) => {
        await page.goto(route, { waitUntil: 'domcontentloaded' });
        const content = page.locator('.v2-content');
        const mobileNavigation = page.getByRole('navigation', { name: 'Mobile navigation', exact: true });
        await expect(content).toBeVisible();
        await expect(mobileNavigation).toBeVisible();

        await content.evaluate((element) => {
          const sentinel = document.createElement('div');
          sentinel.dataset.mobileNavSafeAreaSentinel = 'true';
          sentinel.style.height = '96px';
          sentinel.style.pointerEvents = 'none';
          element.append(sentinel);
        });

        const geometry = await page.evaluate(() => {
          const scrollingElement = document.scrollingElement ?? document.documentElement;
          const navigation = document.querySelector<HTMLElement>('.v2-mobile-nav');
          const sentinel = document.querySelector<HTMLElement>('[data-mobile-nav-safe-area-sentinel]');
          if (!navigation || !sentinel) throw new Error('mobile navigation test fixtures are missing');
          return {
            documentWidth: document.documentElement.scrollWidth,
            navigationTop: navigation.getBoundingClientRect().top,
            scrollHeight: scrollingElement.scrollHeight,
            viewportHeight: window.innerHeight,
            sentinelBottom: sentinel.getBoundingClientRect().bottom,
          };
        });

        expect(geometry.documentWidth).toBeLessThanOrEqual(viewport.width);
        expect(geometry.scrollHeight).toBeGreaterThan(geometry.viewportHeight);

        await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }));
        await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

        const finalGeometry = await page.evaluate(() => {
          const scrollingElement = document.scrollingElement ?? document.documentElement;
          const navigation = document.querySelector<HTMLElement>('.v2-mobile-nav');
          const sentinel = document.querySelector<HTMLElement>('[data-mobile-nav-safe-area-sentinel]');
          if (!navigation || !sentinel) throw new Error('mobile navigation test fixtures are missing');
          return {
            atDocumentEnd: scrollingElement.scrollTop + window.innerHeight >= scrollingElement.scrollHeight - 1,
            navigationTop: navigation.getBoundingClientRect().top,
            sentinelBottom: sentinel.getBoundingClientRect().bottom,
          };
        });

        expect(finalGeometry.atDocumentEnd).toBe(true);
        expect(finalGeometry.sentinelBottom).toBeLessThanOrEqual(finalGeometry.navigationTop);
      });
    }
  });
}
