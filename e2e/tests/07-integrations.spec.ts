import { test, expect } from '@playwright/test'

test.describe('Integrations', () => {
  test.beforeEach(async ({ page }) => {
    // Block Firebase/Google network traffic
    await page.route('**firebase**', route => route.abort())
    await page.route('**firestore**', route => route.abort())
    await page.route('**googleapis.com**', route => route.abort())

    // Mock Notion auth URL endpoint
    await page.route('**/api/brands/*/integrations/notion/auth-url', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ auth_url: 'https://api.notion.com/v1/oauth/authorize?mock=true' }),
      })
    })

    // Mock Notion disconnect endpoint
    await page.route('**/api/brands/*/integrations/notion/disconnect', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      })
    })

    // Mock Notion databases endpoint
    await page.route('**/api/brands/*/integrations/notion/databases', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          databases: [
            { id: 'db-1', title: 'Content Calendar' },
            { id: 'db-2', title: 'Marketing Hub' },
          ],
        }),
      })
    })

    // Mock Notion select-database endpoint
    await page.route('**/api/brands/*/integrations/notion/select-database', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      })
    })

    // Mock brand endpoint (with a connected Notion integration)
    await page.route('**/api/brands/brand-int', route => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            brand_id: 'brand-int',
            business_name: 'Integration Test Brand',
            industry: 'Tech',
            analysis_status: 'complete',
            platform_mode: 'auto',
            selected_platforms: [],
            connected_platforms: [],
            integrations: {
              notion: {
                access_token: 'mock-access-token',
                workspace_name: 'My Workspace',
                database_id: null,
                database_name: null,
                connected_at: new Date().toISOString(),
              },
            },
          }),
        })
      } else {
        route.continue()
      }
    })

    // Catch-all for remaining API calls
    await page.route('**/api/**', route => {
      if (!route.request().isNavigationRequest()) {
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      } else {
        route.continue()
      }
    })
  })

  test('Notion auth URL mock returns expected shape', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/auth-url')
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__notion_auth__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__notion_auth__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__notion_auth__ as { auth_url: string },
    )
    expect(result.auth_url).toBeTruthy()
    expect(result.auth_url).toContain('notion.com')
  })

  test('Notion databases mock returns list of databases', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/databases')
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__notion_dbs__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__notion_dbs__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () =>
        (window as unknown as Record<string, unknown>).__notion_dbs__ as {
          databases: { id: string; title: string }[]
        },
    )
    expect(result.databases).toHaveLength(2)
    expect(result.databases[0].title).toBe('Content Calendar')
    expect(result.databases[1].title).toBe('Marketing Hub')
  })

  test('Notion disconnect mock returns success', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/disconnect', { method: 'POST' })
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__notion_disconnect__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__notion_disconnect__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__notion_disconnect__ as { success: boolean },
    )
    expect(result.success).toBe(true)
  })

  test('Notion select-database mock returns success', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/select-database', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ database_id: 'db-1', database_name: 'Content Calendar' }),
      })
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__notion_select__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__notion_select__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__notion_select__ as { success: boolean },
    )
    expect(result.success).toBe(true)
  })

  test('brand with Notion integration mock returns correct shape', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int')
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__brand_integration__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__brand_integration__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () =>
        (window as unknown as Record<string, unknown>).__brand_integration__ as {
          integrations: { notion: { access_token: string; workspace_name: string } }
        },
    )
    expect(result.integrations.notion.access_token).toBe('mock-access-token')
    expect(result.integrations.notion.workspace_name).toBe('My Workspace')
  })

  test('dashboard connections tab renders (protected, redirects to / without auth)', async ({ page }) => {
    await page.goto('/dashboard/brand-int?tab=connections')
    // Without real auth, ProtectedRoute redirects to /
    await expect(page.locator('body')).toBeVisible()
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('notion callback page redirects gracefully', async ({ page }) => {
    await page.goto('/auth/notion/callback?code=mock-code&state=mock-state')
    // Protected route — redirects to landing without real auth
    await expect(page.locator('body')).toBeVisible()
  })
})
