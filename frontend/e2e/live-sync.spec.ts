import { expect, test } from '@playwright/test';

test('runs synchronization and validates settings against the live backend', async ({ page }) => {
  test.skip(process.env.PLAYWRIGHT_USE_LIVE_API !== '1', 'Requires the isolated live Companion and Immich stack.');

  const serverErrors: string[] = [];
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });

  await page.goto('/settings');
  await page.getByRole('tab', { name: 'Sync' }).click();
  await expect(page.getByText('Current synchronization', { exact: true })).toBeVisible();
  await expect(page.getByText('Synchronization status unavailable')).toHaveCount(0);

  const batchSize = page.getByRole('spinbutton', { name: 'Persistence batch size' });
  await expect(batchSize).toHaveValue('1000');
  await expect(page.getByText('Accepted range: 1–1,000 whole rows.')).toBeVisible();
  await batchSize.fill('1001');
  await expect(page.getByRole('alert').filter({ hasText: 'Persistence batch size' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save runtime settings' })).toBeDisabled();
  await batchSize.fill('1000');

  await page.getByRole('button', { name: 'Start incremental sync' }).click();
  await expect(page.getByText('Synchronization request failed')).toHaveCount(0);
  await expect(page.getByText('Complete.', { exact: true })).toBeVisible();
  const refresh = page.getByRole('button', { name: 'Refresh', exact: true }).first();
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(refresh).toBeEnabled();

  await page.getByRole('tab', { name: 'Tasks' }).click();
  await expect(page.getByText('No active tasks.')).toBeVisible();
  await expect(page.getByText('Task request failed')).toHaveCount(0);
  expect(serverErrors).toEqual([]);
});
