import { expect, test } from '@playwright/test'

test('review queue, shortcuts, archive tab, and empty history copy', async ({ page }) => {
  await page.goto('/#/review')
  await expect(page.getByRole('heading', { name: /Review/ })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Matches' })).toBeVisible()
  await page.keyboard.press('?')
  await expect(page.getByText('Review keyboard shortcuts')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('Review keyboard shortcuts')).toHaveCount(0)
  await page.getByRole('tab', { name: 'History' }).click()
  await expect(page.getByText(/No decisions yet|decisions/i)).toBeVisible()
})
