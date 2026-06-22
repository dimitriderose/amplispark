import { test, expect } from '@playwright/test'

test.describe('Landing page', () => {
  test('renders hero heading', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('h1')).toBeVisible()
  })

  test('has a call-to-action button', async ({ page }) => {
    await page.goto('/')
    const cta = page.getByRole('button').first()
    await expect(cta).toBeVisible()
  })
})
