import { expect, test, type Page } from '@playwright/test';

const tags = [
  { id: 'tag-parent', name: 'Places', color: '#3B82F6', parent_id: null, parent_path: [], asset_count: 4, child_count: 1, children: [] },
  { id: 'tag-child', name: 'Montréal', color: null, parent_id: 'tag-parent', parent_path: ['Places'], asset_count: 2, child_count: 0, children: [] },
];

async function mockTags(page: Page): Promise<void> {
  await page.route('**/api/tags/manage?*', async (route) => {
    await route.fulfill({ json: { items: tags, total: tags.length, page: 1, page_size: 24, pages: 1 } });
  });
}

test('chooses precise, preset, keyboard, and empty colors in the V2 tag modal', async ({ page }) => {
  await mockTags(page);
  await page.goto('/v2/tags');
  await expect(page.getByRole('heading', { level: 1, name: 'Tags' })).toBeVisible();

  await page.getByRole('button', { name: 'Create tag' }).click();
  const tagModal = page.getByRole('dialog', { name: 'Create tag' });
  const trigger = tagModal.locator('#tag-color-1');
  await expect(trigger).toContainText('#9A78FF');

  await trigger.press('Enter');
  const picker = tagModal.getByRole('dialog', { name: 'Choose color' });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole('button', { name: /Red · #EF4444/ })).toBeVisible();
  const colorsInView = picker.getByRole('region', { name: 'Colors in view' });
  await expect(colorsInView).toBeVisible();
  await expect(colorsInView.getByRole('button', { name: '#3B82F6, used by 1 tags' })).toBeVisible();

  await picker.getByRole('button', { name: /Blue · #3B82F6/ }).click();
  await expect(trigger).toContainText('#3B82F6');

  await page.keyboard.press('Escape');
  await expect(picker).toBeHidden();
  await expect(trigger).toBeFocused();

  await trigger.press('Space');
  await expect(picker.getByRole('region', { name: 'Recent colors' }).getByRole('button', { name: 'Recent color #3B82F6' })).toBeVisible();

  const hex = picker.getByRole('textbox', { name: 'HEX color' });
  await hex.fill('#abc');
  await hex.press('Enter');
  await expect(trigger).toContainText('#AABBCC');

  await hex.fill('#12');
  await picker.getByRole('button', { name: /Copy #AABBCC/ }).focus();
  await expect(hex).toHaveValue('#AABBCC');

  const beforePlaneKeyboard = await trigger.textContent();
  await picker.getByRole('slider', { name: 'Saturation and brightness' }).press('Shift+ArrowDown');
  await expect(trigger).not.toHaveText(beforePlaneKeyboard ?? '');

  const beforeKeyboard = await trigger.textContent();
  await picker.getByRole('slider', { name: 'Hue' }).press('Shift+ArrowRight');
  await expect(trigger).not.toHaveText(beforeKeyboard ?? '');

  const beforePointer = await trigger.textContent();
  await picker.getByRole('slider', { name: 'Saturation and brightness' }).click({ position: { x: 35, y: 35 } });
  await expect(trigger).not.toHaveText(beforePointer ?? '');

  await picker.getByRole('button', { name: 'No color' }).click();
  await expect(trigger).toContainText('No color');

  await page.keyboard.press('Escape');
  await expect(picker).toBeHidden();
  await expect(trigger).toBeFocused();
});
