import { test, expect } from '@playwright/test'

test.describe('Onboarding wizard', () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth check so onboard page doesn't redirect
    await page.route('http://localhost:*/api/**', async route => {
      await route.fulfill({ status: 200, json: {} })
    })
  })

  test('onboard page loads without crashing', async ({ page }) => {
    await page.goto('/onboard')
    // Page should load (even if it redirects due to auth state)
    await expect(page).toHaveURL(/\/(onboard|brands|$)/)
  })
})
