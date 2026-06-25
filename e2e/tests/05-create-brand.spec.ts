import { test, expect } from '@playwright/test'

test.describe('Create brand / onboard wizard', () => {
  test.beforeEach(async ({ page }) => {
    // Block Firebase network traffic (external domains only, not local chunks)
    await page.route('https://**firebase**.com/**', route => route.abort())
    await page.route('https://**firebaseapp.com/**', route => route.abort())
    await page.route('https://**firestore.googleapis.com/**', route => route.abort())
    await page.route('https://**googleapis.com/**', route => route.abort())

    // Mock brands list to return empty (so onboard page doesn't redirect away)
    await page.route('http://localhost:*/api/brands**', route => {
      const url = route.request().url()
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ brand_id: 'new-brand-id' }),
        })
      } else if (url.includes('owner_uid')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ brands: [] }),
        })
      } else {
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      }
    })

    // Catch-all for any remaining API calls
    await page.route('http://localhost:*/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }))
  })

  test('landing page loads without crashing', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('h1')).toBeVisible()
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('onboard page loads (redirects to / or shows wizard)', async ({ page }) => {
    await page.goto('/onboard?new=true')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('h1, h2').first()).toBeVisible()
  })

  test('landing page Next button (See how it works) is visible', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('button', { name: /See how it works/i })).toBeVisible()
  })

  test('onboard API mock: POST /api/brands returns brand_id', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    let captured: Record<string, unknown> | null = null
    await page.route('http://localhost:*/api/brands', route => {
      if (route.request().method() === 'POST') {
        captured = { intercepted: true }
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ brand_id: 'mock-brand-xyz' }),
        })
      } else {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ brands: [] }) })
      }
    })

    // Trigger the POST manually to verify mock works
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_name: 'Test', description: 'A test brand for e2e' }),
      })
      return res.json() as Promise<{ brand_id: string }>
    }) as { brand_id: string }
    expect(result.brand_id).toBe('mock-brand-xyz')
    expect(captured).not.toBeNull()
  })

  test('wizard step indicator: landing page shows numbered steps', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('div').filter({ hasText: /^01$/ }).first()).toBeVisible()
    await expect(page.locator('div').filter({ hasText: /^02$/ }).first()).toBeVisible()
    await expect(page.locator('div').filter({ hasText: /^03$/ }).first()).toBeVisible()
  })

  test('landing page has a "Describe your brand" step', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(/Describe your brand/i)).toBeVisible()
  })
})
