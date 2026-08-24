import { expect, test, type Page } from '@playwright/test';

const useLiveApi = process.env.PLAYWRIGHT_USE_LIVE_API === '1';

async function mockHealthyStatus(page: Page): Promise<void> {
  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      json: {
        status: 'ok',
        ready: true,
        environment: 'test',
        safe_mode: true,
        dependencies: { immich: { status: 'ok', configured: true, latency_ms: 3.2 } },
      },
    });
  });
  await page.route('**/api/version', async (route) => {
    await route.fulfill({
      json: { name: 'immich-companion', version: 'browser-test', environment: 'test' },
    });
  });
  await page.route('**/api/capabilities', async (route) => {
    await route.fulfill({
      json: {
        destructive_actions: false,
        immich_api: true,
        implemented: ['health', 'version', 'capabilities'],
        planned: ['sync', 'search'],
      },
    });
  });
}

test('shows a healthy, safe companion status', async ({ page }) => {
  if (!useLiveApi) await mockHealthyStatus(page);

  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'Companion status' })).toBeVisible();
  await expect(page.getByText('test environment', { exact: true })).toBeVisible();
  await expect(page.getByText('Safe mode', { exact: true })).toBeVisible();
  await expect(page.getByText('Operational', { exact: true })).toBeVisible();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
});

test('shows a recoverable backend error', async ({ page }) => {
  test.skip(useLiveApi, 'The live environment is expected to be healthy.');

  await page.route('**/api/**', async (route) => {
    await route.fulfill({ status: 503, body: 'unavailable' });
  });
  await page.goto('/');

  await expect(page.getByRole('alert')).toContainText('backend is unavailable');
  await expect(page.getByRole('button', { name: 'Retry status check' })).toBeVisible();
});
