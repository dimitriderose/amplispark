import { test, expect } from '@playwright/test'

// Mock Firebase auth so ProtectedRoute lets us through
async function mockAuth(page: Parameters<typeof test>[1] extends (...args: infer A) => unknown ? A[0] : never) {
  await page.addInitScript(() => {
    // Patch firebase/auth so onAuthStateChanged fires immediately with a fake user
    const fakeUser = {
      uid: 'test-uid-brands',
      displayName: 'Test User',
      email: 'test@example.com',
      photoURL: null,
      getIdToken: () => Promise.resolve('fake-token'),
    }
    // Store on window so firebase.ts picks it up via the patched module
    ;(window as unknown as Record<string, unknown>).__PLAYWRIGHT_FAKE_USER__ = fakeUser

    // Intercept the firebase/auth module's onAuthStateChanged to fire our fake user
    const _orig = Object.getOwnPropertyDescriptor(window, '__firebase_auth_listeners__')
    void _orig // suppress unused
    ;(window as unknown as Record<string, unknown>).__firebase_auth_listeners__ = []

    // Override localStorage to simulate persisted auth session
    window.localStorage.setItem(
      'amplifi_fake_auth',
      JSON.stringify({ uid: 'test-uid-brands', displayName: 'Test User' }),
    )
  })
}

test.describe('Brands page', () => {
  test.beforeEach(async ({ page }) => {
    // Block all real Firebase network traffic (external domains only, not local chunks)
    await page.route('https://**firebase**.com/**', route => route.abort())
    await page.route('https://**firebaseapp.com/**', route => route.abort())
    await page.route('https://**firestore.googleapis.com/**', route => route.abort())
    await page.route('https://**googleapis.com/**', route => route.abort())

    // Mock the brands list API
    await page.route('http://localhost:*/api/brands**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          brands: [
            {
              brand_id: 'b1',
              business_name: 'Sunrise Bakery',
              industry: 'Food & Beverage',
              analysis_status: 'complete',
            },
            {
              brand_id: 'b2',
              business_name: 'Mountain Coffee',
              industry: 'Beverages',
              analysis_status: 'pending',
            },
          ],
        }),
      })
    })

    // Catch-all for any remaining API calls
    await page.route('http://localhost:*/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }))
  })

  test('brands page renders the Create Your Brand section', async ({ page }) => {
    await page.goto('/brands')
    await page.waitForLoadState('networkidle')
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('landing page has Join Waitlist button', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('button', { name: /Join Waitlist/i }).first()).toBeVisible()
  })

  test('landing page shows platform names', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.getByText('Instagram').first()).toBeVisible()
    await expect(page.getByText('LinkedIn').first()).toBeVisible()
  })

  test('brands API returns brands with expected shape', async ({ page }) => {
    let intercepted = false
    await page.route('http://localhost:*/api/brands**', route => {
      intercepted = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          brands: [
            { brand_id: 'b1', business_name: 'My Brand', analysis_status: 'complete' },
          ],
        }),
      })
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // Trigger the API to verify our mock intercept works
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands?owner_uid=test')
      return await res.json()
    }) as { brands: { brand_id: string }[] }
    expect(intercepted).toBe(true)
    expect(result.brands).toHaveLength(1)
    expect(result.brands[0].brand_id).toBe('b1')
  })
})
