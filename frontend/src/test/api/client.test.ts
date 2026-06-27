import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

vi.mock('../../api/firebase', () => ({
  getIdToken: vi.fn().mockResolvedValue('mock-token'),
  getUid: vi.fn().mockReturnValue('mock-uid'),
}))

vi.mock('../../utils/downloads', () => ({
  downloadBlob: vi.fn(),
}))

import { api } from '../../api/client'
import { getIdToken, getUid } from '../../api/firebase'
import { downloadBlob } from '../../utils/downloads'

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const responseBody = typeof body === 'string' ? body : JSON.stringify(body)
  const responseHeaders = new Headers({ 'Content-Type': 'application/json', ...headers })
  const res = new Response(responseBody, { status, headers: responseHeaders })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
}


describe('api client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getIdToken).mockResolvedValue('mock-token')
    vi.mocked(getUid).mockReturnValue('mock-uid')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('auth headers', () => {
    it('sends Authorization header when token is available', async () => {
      mockFetch(200, { brands: [] })
      await api.listBrands('uid-123')
      const headers = (vi.mocked(fetch).mock.calls[0][1] as RequestInit).headers as Record<string, string>
      expect(headers['Authorization']).toBe('Bearer mock-token')
    })

    it('falls back to X-User-UID header when no token', async () => {
      vi.mocked(getIdToken).mockResolvedValue(null as unknown as string)
      vi.mocked(getUid).mockReturnValue('uid-fallback')
      mockFetch(200, { brands: [] })
      await api.listBrands('uid-123')
      const headers = (vi.mocked(fetch).mock.calls[0][1] as RequestInit).headers as Record<string, string>
      expect(headers['X-User-UID']).toBe('uid-fallback')
    })

    it('sends no auth headers when both token and uid are absent', async () => {
      vi.mocked(getIdToken).mockResolvedValue(null as unknown as string)
      vi.mocked(getUid).mockReturnValue(null)
      mockFetch(200, { brands: [] })
      await api.listBrands('uid-123')
      const headers = (vi.mocked(fetch).mock.calls[0][1] as RequestInit).headers as Record<string, string>
      expect(headers['Authorization']).toBeUndefined()
      expect(headers['X-User-UID']).toBeUndefined()
    })
  })

  describe('handleResponse', () => {
    it('throws with detail message on non-ok JSON response', async () => {
      mockFetch(400, { detail: 'Bad input' })
      await expect(api.listBrands('uid')).rejects.toThrow('Bad input')
    })

    it('throws with error field when detail is absent', async () => {
      mockFetch(400, { error: 'something went wrong' })
      await expect(api.listBrands('uid')).rejects.toThrow('something went wrong')
    })

    it('throws HTTP status when no detail or error field', async () => {
      mockFetch(500, {})
      await expect(api.listBrands('uid')).rejects.toThrow('HTTP 500')
    })

    it('falls back to text body when error response is not JSON', async () => {
      const res = new Response('plain error text', { status: 500 })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await expect(api.listBrands('uid')).rejects.toThrow('plain error text')
    })

    it('returns undefined for empty response (content-length: 0)', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      const result = await api.deleteBrandAsset('brand-1', 0)
      expect(result).toBeUndefined()
    })

    it('returns data on successful response', async () => {
      mockFetch(200, { brands: [{ brand_id: 'b1' }] })
      const result = await api.listBrands('uid-123')
      expect(result).toEqual({ brands: [{ brand_id: 'b1' }] })
    })
  })

  describe('brands', () => {
    it('listBrands calls correct endpoint', async () => {
      mockFetch(200, { brands: [] })
      await api.listBrands('uid-123')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('/api/brands?owner_uid=uid-123'),
        expect.any(Object),
      )
    })

    it('createBrand posts to /api/brands', async () => {
      mockFetch(200, { brand_id: 'new-brand' })
      await api.createBrand({ name: 'Test' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('getBrand calls correct endpoint', async () => {
      mockFetch(200, { brand_id: 'brand-1' })
      await api.getBrand('brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1',
        expect.any(Object),
      )
    })

    it('updateBrand uses PUT method', async () => {
      mockFetch(200, { brand_id: 'brand-1' })
      await api.updateBrand('brand-1', { name: 'Updated' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1',
        expect.objectContaining({ method: 'PUT' }),
      )
    })

    it('deleteBrandAsset uses DELETE method', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await api.deleteBrandAsset('brand-1', 2)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/assets/2',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  describe('plans', () => {
    it('listPlans calls correct endpoint', async () => {
      mockFetch(200, { plans: [] })
      await api.listPlans('brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans',
        expect.any(Object),
      )
    })

    it('createPlan posts with num_days', async () => {
      mockFetch(200, { plan_id: 'plan-1', status: 'complete', days: [] })
      await api.createPlan('brand-1', 5)
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.num_days).toBe(5)
    })

    it('createPlan includes platforms when provided', async () => {
      mockFetch(200, { plan_id: 'plan-1', status: 'complete', days: [] })
      await api.createPlan('brand-1', 7, undefined, ['instagram', 'linkedin'])
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.platforms).toEqual(['instagram', 'linkedin'])
    })

    it('createPlan omits platforms when empty array is provided', async () => {
      mockFetch(200, { plan_id: 'plan-1', status: 'complete', days: [] })
      await api.createPlan('brand-1', 7, undefined, [])
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.platforms).toBeUndefined()
    })

    it('getPlan calls correct endpoint', async () => {
      mockFetch(200, { plan_profile: {} })
      await api.getPlan('brand-1', 'plan-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1',
        expect.any(Object),
      )
    })
  })

  describe('posts', () => {
    it('listPosts includes plan_id when provided', async () => {
      mockFetch(200, { posts: [] })
      await api.listPosts('brand-1', 'plan-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('plan_id=plan-1'),
        expect.any(Object),
      )
    })

    it('listPosts omits plan_id when not provided', async () => {
      mockFetch(200, { posts: [] })
      await api.listPosts('brand-1')
      const url = (vi.mocked(fetch).mock.calls[0][0] as string)
      expect(url).not.toContain('plan_id')
    })

    it('approvePost uses POST method', async () => {
      mockFetch(200, { status: 'approved' })
      await api.approvePost('brand-1', 'post-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/posts/post-1/approve',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('getPost calls correct endpoint', async () => {
      mockFetch(200, { post_id: 'post-1' })
      await api.getPost('brand-1', 'post-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('/api/posts/post-1'),
        expect.any(Object),
      )
    })

    it('updatePost uses PATCH method', async () => {
      mockFetch(200, { post_id: 'post-1' })
      await api.updatePost('brand-1', 'post-1', { caption: 'new caption' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/posts/post-1',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    it('reviewPost appends force param when true', async () => {
      mockFetch(200, { status: 'reviewed' })
      await api.reviewPost('brand-1', 'post-1', true)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('force=true'),
        expect.any(Object),
      )
    })

    it('reviewPost omits force param when false', async () => {
      mockFetch(200, { status: 'reviewed' })
      await api.reviewPost('brand-1', 'post-1', false)
      const url = vi.mocked(fetch).mock.calls[0][0] as string
      expect(url).not.toContain('force=true')
    })
  })

  describe('waitlist and user', () => {
    it('joinWaitlist posts email without auth header', async () => {
      mockFetch(200, { status: 'joined' })
      await api.joinWaitlist('test@example.com')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/waitlist',
        expect.objectContaining({ method: 'POST' }),
      )
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.email).toBe('test@example.com')
    })

    it('getUser calls /api/users/me', async () => {
      mockFetch(200, { role: 'beta', beta_expires_at: null, quick_posts_this_month: 0, calendars_this_month: 0, days_remaining: 28, quick_posts_limit: 8, calendars_limit: 4 })
      const result = await api.getUser()
      expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/users/me', expect.any(Object))
      expect(result.role).toBe('beta')
    })
  })

  describe('notifications', () => {
    it('getUnreadCount calls correct endpoint', async () => {
      mockFetch(200, { unread_count: 3 })
      await api.getUnreadCount()
      expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/notifications/unread-count', expect.any(Object))
    })

    it('markAllNotificationsRead uses POST method', async () => {
      mockFetch(200, { status: 'ok', updated: 2 })
      await api.markAllNotificationsRead()
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/notifications/read-all',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  describe('export', () => {
    it('exportPost triggers downloadBlob on success', async () => {
      const blob = new Blob(['zip-content'])
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(blob, { status: 200 })))
      await api.exportPost('post-1', 'brand-1')
      expect(vi.mocked(downloadBlob)).toHaveBeenCalledWith(expect.any(Blob), 'amplifi_post_post-1.zip')
    })

    it('exportPost throws on non-ok response', async () => {
      mockFetch(404, { detail: 'Not found' })
      await expect(api.exportPost('post-1', 'brand-1')).rejects.toThrow('Not found')
    })

    it('exportPlan triggers downloadBlob on success', async () => {
      const blob = new Blob(['zip-content'])
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(blob, { status: 200 })))
      await api.exportPlan('plan-1', 'brand-1')
      expect(vi.mocked(downloadBlob)).toHaveBeenCalledWith(expect.any(Blob), 'amplifi_export_plan-1.zip')
    })

    it('downloadCalendar triggers downloadBlob with ics filename', async () => {
      const blob = new Blob(['ical-content'])
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(blob, { status: 200 })))
      await api.downloadCalendar('brand-1', 'plan-1')
      expect(vi.mocked(downloadBlob)).toHaveBeenCalledWith(expect.any(Blob), 'amplifi_content_plan.ics')
    })
  })

  describe('upload methods', () => {
    it('uploadBrandAsset sends FormData without Content-Type header (with auth token)', async () => {
      mockFetch(200, { asset_url: 'https://storage.example.com/asset.jpg' })
      const formData = new FormData()
      await api.uploadBrandAsset('brand-1', formData)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/upload',
        expect.objectContaining({ method: 'POST', body: formData }),
      )
    })

    it('uploadBrandAsset uses UID header when no token', async () => {
      vi.mocked(getIdToken).mockResolvedValue(null as unknown as string)
      vi.mocked(getUid).mockReturnValue('uid-fallback')
      mockFetch(200, { asset_url: 'https://storage.example.com/asset.jpg' })
      const formData = new FormData()
      await api.uploadBrandAsset('brand-1', formData)
      const headers = (vi.mocked(fetch).mock.calls[0][1] as RequestInit).headers as Record<string, string>
      expect(headers['X-User-UID']).toBe('uid-fallback')
    })

    it('uploadDayPhoto calls correct endpoint', async () => {
      mockFetch(200, { custom_photo_url: 'https://example.com/photo.jpg', custom_photo_gcs_uri: 'gs://bucket/photo.jpg' })
      const formData = new FormData()
      await api.uploadDayPhoto('brand-1', 'plan-1', 0, formData)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/days/0/photo',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('uploadVideoForRepurpose calls correct endpoint', async () => {
      mockFetch(200, { job_id: 'job-1' })
      const formData = new FormData()
      await api.uploadVideoForRepurpose('brand-1', formData)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/video-repurpose',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  describe('media editing', () => {
    it('editPostMedia posts with edit_prompt body', async () => {
      mockFetch(200, { image_url: 'https://example.com/edited.jpg' })
      await api.editPostMedia('brand-1', 'post-1', { edit_prompt: 'make it blue' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/posts/post-1/edit-media',
        expect.objectContaining({ method: 'POST' }),
      )
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.edit_prompt).toBe('make it blue')
    })

    it('resetPostMedia calls correct endpoint', async () => {
      mockFetch(200, { image_url: 'https://example.com/original.jpg' })
      await api.resetPostMedia('brand-1', 'post-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/posts/post-1/edit-media/reset',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('resetPostMedia appends target param when provided', async () => {
      mockFetch(200, { image_url: 'https://example.com/original.jpg' })
      await api.resetPostMedia('brand-1', 'post-1', 'slide_0')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('target=slide_0'),
        expect.any(Object),
      )
    })
  })

  describe('integrations and misc', () => {
    it('connectSocial posts to connect-social endpoint', async () => {
      mockFetch(200, { platform: 'instagram', voice_analysis: {} })
      await api.connectSocial('brand-1', 'instagram', 'token-123')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/connect-social',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('regeneratePost calls correct endpoint', async () => {
      mockFetch(200, { generate_url: '/generate/plan-1/0?brand_id=brand-1' })
      await api.regeneratePost('brand-1', 'post-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/posts/post-1/regenerate',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('emailCalendar posts email to correct endpoint', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await api.emailCalendar('brand-1', 'plan-1', 'test@example.com')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/calendar/email',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('refreshPlanResearch calls correct endpoint', async () => {
      mockFetch(200, { trend_summary: 'trending topics' })
      await api.refreshPlanResearch('brand-1', 'plan-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/refresh-research',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('getVideoJob calls correct endpoint', async () => {
      mockFetch(200, { job_id: 'job-1', status: 'complete' })
      await api.getVideoJob('job-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/video-jobs/job-1', expect.any(Object))
    })

    it('setBrandLogo sends PATCH with logo_url', async () => {
      mockFetch(200, { brand_id: 'brand-1' })
      await api.setBrandLogo('brand-1', 'https://example.com/logo.png')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/logo',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })

    it('getNotionAuthUrl calls correct endpoint', async () => {
      mockFetch(200, { auth_url: 'https://notion.com/oauth' })
      await api.getNotionAuthUrl('brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/integrations/notion/auth-url',
        expect.any(Object),
      )
    })

    it('disconnectNotion uses POST method', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await api.disconnectNotion('brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/integrations/notion/disconnect',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('getNotionDatabases calls correct endpoint', async () => {
      mockFetch(200, { databases: [{ id: 'db-1', title: 'My DB' }] })
      await api.getNotionDatabases('brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/integrations/notion/databases',
        expect.any(Object),
      )
    })

    it('selectNotionDatabase posts with database_id and database_name', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await api.selectNotionDatabase('brand-1', 'db-1', 'My DB')
      const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)
      expect(body.database_id).toBe('db-1')
      expect(body.database_name).toBe('My DB')
    })

    it('exportToNotion posts to correct endpoint', async () => {
      mockFetch(200, { exported: 5, total: 5, results: [] })
      await api.exportToNotion('brand-1', 'plan-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/export/notion',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('listNotifications uses default limit of 10', async () => {
      mockFetch(200, { notifications: [], unread_count: 0 })
      await api.listNotifications()
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('limit=10'),
        expect.any(Object),
      )
    })

    it('getVideoRepurposeJob calls correct endpoint', async () => {
      mockFetch(200, { job_id: 'job-1', status: 'complete', clips: [] })
      await api.getVideoRepurposeJob('job-1', 'brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('/api/video-repurpose-jobs/job-1'),
        expect.any(Object),
      )
    })

    it('analyzeBrand posts to analyze endpoint', async () => {
      mockFetch(200, { brand_id: 'brand-1' })
      await api.analyzeBrand('brand-1', { website_url: 'https://example.com' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/analyze',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('updateDay uses PUT method', async () => {
      mockFetch(200, { plan_profile: {} })
      await api.updateDay('brand-1', 'plan-1', 2, { content_theme: 'lifestyle' })
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/days/2',
        expect.objectContaining({ method: 'PUT' }),
      )
    })

    it('deleteDayPhoto uses DELETE method', async () => {
      const res = new Response('', { status: 200, headers: { 'content-length': '0' } })
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
      await api.deleteDayPhoto('brand-1', 'plan-1', 0)
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/brands/brand-1/plans/plan-1/days/0/photo',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('generateVideo posts with tier and brand_id params', async () => {
      mockFetch(200, { job_id: 'job-1', status: 'pending' })
      await api.generateVideo('post-1', 'fast', 'brand-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.stringContaining('tier=fast'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('markNotificationRead uses PATCH method', async () => {
      mockFetch(200, { status: 'ok', notification_id: 'notif-1' })
      await api.markNotificationRead('notif-1')
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/notifications/notif-1/read',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })
})
