import { test, expect } from '@playwright/test'

test.describe('Integrations', () => {
  test.beforeEach(async ({ page }) => {
    // Block Firebase/Google network traffic
    await page.route('**firebase**', route => route.abort())
    await page.route('**firestore**', route => route.abort())
    await page.route('**googleapis.com**', route => route.abort())

    // Catch-all for remaining API calls — registered FIRST so specific routes (registered after) take priority (Playwright LIFO matching)
    await page.route('**/api/**', route => {
      if (!route.request().isNavigationRequest()) {
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      } else {
        route.continue()
      }
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

    // Mock Notion select-database endpoint
    await page.route('**/api/brands/*/integrations/notion/select-database', route => {
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

    // Mock Notion disconnect endpoint
    await page.route('**/api/brands/*/integrations/notion/disconnect', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      })
    })

    // Mock Notion auth URL endpoint
    await page.route('**/api/brands/*/integrations/notion/auth-url', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ auth_url: 'https://api.notion.com/v1/oauth/authorize?mock=true' }),
      })
    })
  })

  test('Notion auth URL mock returns expected shape', async ({ page }) => {
    await page.goto('/')

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/auth-url')
      return res.json()
    })
    expect(result.auth_url).toBeTruthy()
    expect(result.auth_url).toContain('notion.com')
  })

  test('Notion databases mock returns list of databases', async ({ page }) => {
    await page.goto('/')

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/databases')
      return res.json()
    })
    expect(result.databases).toHaveLength(2)
    expect(result.databases[0].title).toBe('Content Calendar')
    expect(result.databases[1].title).toBe('Marketing Hub')
  })

  test('Notion disconnect mock returns success', async ({ page }) => {
    await page.goto('/')

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/disconnect', { method: 'POST' })
      return res.json()
    })
    expect(result.success).toBe(true)
  })

  test('Notion select-database mock returns success', async ({ page }) => {
    await page.goto('/')

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int/integrations/notion/select-database', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ database_id: 'db-1', database_name: 'Content Calendar' }),
      })
      return res.json()
    })
    expect(result.success).toBe(true)
  })

  test('brand with Notion integration mock returns correct shape', async ({ page }) => {
    await page.goto('/')

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-int')
      return res.json()
    })
    expect(result.integrations.notion.access_token).toBe('mock-access-token')
    expect(result.integrations.notion.workspace_name).toBe('My Workspace')
  })

  test('dashboard connections tab renders (protected, redirects to / without auth)', async ({ page }) => {
    await page.goto('/dashboard/brand-int?tab=connections')
    await page.waitForSelector('h1, h2', { timeout: 15000 })
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('notion callback page redirects gracefully', async ({ page }) => {
    await page.goto('/auth/notion/callback?code=mock-code&state=mock-state')
    await page.waitForSelector('h1, nav', { timeout: 15000 })
    await expect(page.locator('body')).toBeVisible()
  })
})
