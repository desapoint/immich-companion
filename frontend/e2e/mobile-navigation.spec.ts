import { expect, test } from '@playwright/test';

const mobileDestinations = [
  { label: 'Trash', path: '/restore' },
  { label: 'Similarity debug', path: '/similarity-debug' },
  { label: 'Albums', path: '/albums' },
  { label: 'Tags', path: '/tags' },
  { label: 'Settings', path: '/settings' },
  { label: 'API Docs', path: '/docs' },
] as const;

const mobileSizes = [
  { name: 'tablet mobile', width: 600, height: 960 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'small mobile', width: 360, height: 800 },
] as const;

for (const size of mobileSizes) {
  test.describe(`${size.name} navigation`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test('keeps the mobile navigation usable without horizontal overflow', async ({ page }) => {
      await page.goto('/');

      const mobileNavigation = page.getByRole('navigation', { name: 'Mobile navigation', exact: true });
      await expect(mobileNavigation).toBeVisible();

      const touchTargets = mobileNavigation.locator('a, button');
      await expect(touchTargets).toHaveCount(5);
      for (let index = 0; index < 5; index += 1) {
        const box = await touchTargets.nth(index).boundingBox();
        expect(box, `mobile navigation target ${index + 1}`).not.toBeNull();
        expect(box!.width).toBeGreaterThanOrEqual(44);
        expect(box!.height).toBeGreaterThanOrEqual(44);
      }

      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size.width);
    });

    test('opens More, exposes every destination, and closes on Escape', async ({ page }) => {
      await page.goto('/');

      const moreButton = page.getByRole('button', { name: 'More' });
      const menu = page.getByRole('dialog', { name: 'More navigation' });
      await expect(moreButton).toHaveAttribute('aria-expanded', 'false');
      await moreButton.click();

      await expect(moreButton).toHaveAttribute('aria-expanded', 'true');
      await expect(menu).toBeVisible();
      await expect(menu.getByRole('link')).toHaveCount(mobileDestinations.length);
      expect(await menu.getByRole('link').allTextContents()).toEqual(
        mobileDestinations.map((destination) => destination.label),
      );

      const menuBox = await menu.boundingBox();
      const navigationBox = await page
        .getByRole('navigation', { name: 'Mobile navigation', exact: true })
        .boundingBox();
      expect(menuBox).not.toBeNull();
      expect(navigationBox).not.toBeNull();
      expect(menuBox!.y + menuBox!.height).toBeLessThanOrEqual(navigationBox!.y);

      await page.keyboard.press('Escape');
      await expect(menu).toBeHidden();
      await expect(moreButton).toHaveAttribute('aria-expanded', 'false');
    });

    for (const destination of mobileDestinations) {
      test(`navigates to ${destination.label} and highlights the current destination`, async ({ page }) => {
        await page.goto('/');

        const moreButton = page.getByRole('button', { name: 'More' });
        const menu = page.getByRole('dialog', { name: 'More navigation' });
        await moreButton.click();
        await menu.getByRole('link', { name: destination.label, exact: true }).click();

        await expect(page).toHaveURL(new RegExp(`${destination.path}$`));
        await expect(menu).toBeHidden();
        await expect(moreButton).toHaveAttribute('aria-expanded', 'false');

        await moreButton.click();
        await expect(menu.getByRole('link', { name: destination.label, exact: true })).toHaveAttribute(
          'aria-current',
          'page',
        );
      });
    }
  });
}
