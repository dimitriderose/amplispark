import { test, expect } from '@playwright/test'

const MOCK_POSTS = [
  {
    post_id: 'post-1',
    brand_id: 'brand-abc',
    plan_id: 'plan-xyz',
    day_index: 0,
    platform: 'Instagram',
    caption: 'Check out our amazing new product! #launch #innovation',
    hashtags: ['#launch', '#innovation'],
    status: 'generated',
    image_url: null,
    created_at: new Date().toISOString(),
  },
  {
    post_id: 'post-2',
    brand_id: 'brand-abc',
    plan_id: 'plan-xyz',
    day_index: 1,
    platform: 'LinkedIn',
    caption: 'Thrilled to announce our company milestone. Here is what we learned.',
    hashtags: ['#milestone'],
    status: 'approved',
    image_url: null,
    created_at: new Date().toISOString(),
  },
]

const MOCK_PLAN = {
  plan_id: 'plan-xyz',
  brand_id: 'brand-abc',
  num_days: 7,
  days: [
    { day_index: 0, platform: 'Instagram', theme: 'Product Launch', content_pillar: 'Promotion', anchor_event: null, custom_photo_url: null },
    { day_index: 1, platform: 'LinkedIn', theme: 'Company Milestone', content_pillar: 'Education', anchor_event: null, custom_photo_url: null },
  ],
  created_at: new Date().toISOString(),
}

test.describe('Post actions', () => {
  test.beforeEach(async ({ page }) => {
    // Block Firebase/Google network traffic
    await page.route('**firebase**', route => route.abort())
    await page.route('**firestore**', route => route.abort())
    await page.route('**googleapis.com**', route => route.abort())

    // Mock posts endpoint
    await page.route('**/api/posts**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ posts: MOCK_POSTS }),
      })
    })

    // Mock individual post endpoints (approve, review)
    await page.route('**/api/brands/*/posts/*/approve', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ post_id: 'post-1', status: 'approved' }),
      })
    })

    await page.route('**/api/brands/*/posts/*/review', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ post_id: 'post-1', score: 92, feedback: 'Great post!' }),
      })
    })

    // Mock plans endpoint
    await page.route('**/api/brands/*/plans/**', route => {
      const url = route.request().url()
      if (url.match(/\/plans\/[^/]+$/)) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_PLAN),
        })
      } else if (url.match(/\/plans$/)) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ plans: [MOCK_PLAN] }),
        })
      } else {
        route.continue()
      }
    })

    // Mock brand endpoint
    await page.route('**/api/brands/brand-abc', route => {
      if (route.request().method() === 'GET') {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            brand_id: 'brand-abc',
            business_name: 'Test Brand',
            industry: 'Tech',
            analysis_status: 'complete',
            platform_mode: 'auto',
            selected_platforms: [],
            connected_platforms: [],
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

  test('posts API mock returns post list with expected shape', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/posts?brand_id=brand-abc')
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__posts_result__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__posts_result__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__posts_result__ as { posts: typeof MOCK_POSTS },
    )
    expect(result.posts).toHaveLength(2)
    expect(result.posts[0].post_id).toBe('post-1')
    expect(result.posts[0].platform).toBe('Instagram')
    expect(result.posts[1].status).toBe('approved')
  })

  test('posts API mock: post has caption and platform fields', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/posts?brand_id=brand-abc&plan_id=plan-xyz')
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__posts_fields__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__posts_fields__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__posts_fields__ as { posts: typeof MOCK_POSTS },
    )
    const post = result.posts[0]
    expect(post).toHaveProperty('caption')
    expect(post).toHaveProperty('platform')
    expect(post.caption).toContain('#launch')
  })

  test('approve endpoint mock returns approved status', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-abc/posts/post-1/approve', { method: 'POST' })
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__approve_result__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__approve_result__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__approve_result__ as { status: string },
    )
    expect(result.status).toBe('approved')
  })

  test('review endpoint mock returns score', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(async () => {
      const res = await fetch('/api/brands/brand-abc/posts/post-1/review', { method: 'POST' })
      const data = await res.json()
      ;(window as unknown as Record<string, unknown>).__review_result__ = data
    })

    await page.waitForFunction(() => (window as unknown as Record<string, unknown>).__review_result__ !== undefined, { timeout: 5000 })
    const result = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__review_result__ as { score: number; feedback: string },
    )
    expect(result.score).toBe(92)
    expect(result.feedback).toBe('Great post!')
  })

  test('export page renders without crashing (protected, redirects to /)', async ({ page }) => {
    await page.goto('/export/brand-abc?plan_id=plan-xyz')
    // Protected route — without real auth, redirects to landing
    await expect(page.locator('body')).toBeVisible()
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('landing page hero heading is present', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('h1')).toBeVisible()
  })
})
