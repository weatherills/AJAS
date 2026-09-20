import { expect, test } from '@playwright/test'

test('matching job feed shows Greenhouse/Lever copy', async ({ page }) => {
  await page.goto('/#/jobs')
  await expect(page.getByRole('heading', { name: 'Jobs', exact: true })).toBeVisible()
  await expect(page.getByText(/Greenhouse and Lever/i)).toBeVisible()
})

test('review queue heading is visible', async ({ page }) => {
  await page.goto('/#/review')
  await expect(page.getByRole('heading', { name: 'Review & Decision', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Matches' })).toBeVisible()
})

test('auto-apply queue heading is visible', async ({ page }) => {
  await page.goto('/#/apply')
  await expect(page.getByRole('heading', { name: 'Auto-Apply', exact: true })).toBeVisible()
})

test('email inbox heading is visible', async ({ page }) => {
  await page.goto('/#/email')
  await expect(page.getByRole('heading', { name: 'Email', exact: true })).toBeVisible()
})
