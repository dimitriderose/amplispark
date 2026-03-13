async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.detail || err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  listBrands: (ownerUid: string) =>
    request<{ brands: Record<string, unknown>[] }>(`/api/brands?owner_uid=${encodeURIComponent(ownerUid)}`),
  createBrand: (data: object) =>
    request('/api/brands', { method: 'POST', body: JSON.stringify(data) }),
  analyzeBrand: (brandId: string, data: object) =>
    request(`/api/brands/${brandId}/analyze`, { method: 'POST', body: JSON.stringify(data) }),
  getBrand: (brandId: string) => request(`/api/brands/${brandId}`),
  updateBrand: (brandId: string, data: object) =>
    request(`/api/brands/${brandId}`, { method: 'PUT', body: JSON.stringify(data) }),
  uploadBrandAsset: (brandId: string, formData: FormData) =>
    fetch(`/api/brands/${brandId}/upload`, { method: 'POST', body: formData }).then(r => r.json()),
  deleteBrandAsset: (brandId: string, assetIndex: number) =>
    request(`/api/brands/${brandId}/assets/${assetIndex}`, { method: 'DELETE' }),
  setBrandLogo: (brandId: string, logoUrl: string | null) =>
    request(`/api/brands/${brandId}/logo`, {
      method: 'PATCH',
      body: JSON.stringify({ logo_url: logoUrl }),
    }),

  listPlans: (brandId: string) => request(`/api/brands/${brandId}/plans`),
  createPlan: (brandId: string, numDays = 7, businessEvents?: string, platforms?: string[]) =>
    request(`/api/brands/${brandId}/plans`, {
      method: 'POST',
      body: JSON.stringify({
        num_days: numDays,
        business_events: businessEvents || null,
        ...(platforms && platforms.length > 0 ? { platforms } : {}),
      }),
    }),
  getPlan: (brandId: string, planId: string) => request(`/api/brands/${brandId}/plans/${planId}`),
  updateDay: (brandId: string, planId: string, dayIndex: number, data: object) =>
    request(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}`, { method: 'PUT', body: JSON.stringify(data) }),

  listPosts: (brandId: string, planId?: string) =>
    request(`/api/posts?brand_id=${brandId}${planId ? `&plan_id=${planId}` : ''}`),
  getPost: (brandId: string, postId: string) =>
    request(`/api/posts/${postId}?brand_id=${brandId}`),
  updatePost: (brandId: string, postId: string, data: { caption?: string; hashtags?: string[] }) =>
    request(`/api/brands/${brandId}/posts/${postId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  reviewPost: (brandId: string, postId: string, force = false) =>
    request(`/api/brands/${brandId}/posts/${postId}/review${force ? '?force=true' : ''}`, { method: 'POST' }),
  approvePost: (brandId: string, postId: string) =>
    request(`/api/brands/${brandId}/posts/${postId}/approve`, { method: 'POST' }),
  exportPost: (postId: string, brandId: string) =>
    fetch(`/api/posts/${postId}/export?brand_id=${encodeURIComponent(brandId)}`)
      .then(async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ error: r.statusText }))
          throw new Error(err.detail || err.error || `HTTP ${r.status}`)
        }
        const blob = await r.blob()
        const disposition = r.headers.get('Content-Disposition') || ''
        const match = disposition.match(/filename=(.+)/)
        const filename = match ? match[1] : `amplifi_post_${postId}.zip`
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
      }),
  exportPlan: (planId: string, brandId: string) =>
    fetch(`/api/export/${planId}?brand_id=${encodeURIComponent(brandId)}`, { method: 'POST' })
      .then(async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ error: r.statusText }))
          throw new Error(err.error || `HTTP ${r.status}`)
        }
        const blob = await r.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `amplifi_export_${planId}.zip`
        a.click()
        URL.revokeObjectURL(url)
      }),

  uploadDayPhoto: (brandId: string, planId: string, dayIndex: number, formData: FormData) =>
    fetch(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}/photo`, {
      method: 'POST',
      body: formData,
    }).then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        throw new Error(err.detail || `HTTP ${r.status}`)
      }
      return r.json()
    }),

  deleteDayPhoto: (brandId: string, planId: string, dayIndex: number) =>
    request(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}/photo`, { method: 'DELETE' }),

  generateVideo: (postId: string, tier = 'fast', brandId = '') =>
    request(`/api/posts/${postId}/generate-video?tier=${tier}&brand_id=${brandId}`, { method: 'POST' }),
  getVideoJob: (jobId: string) => request(`/api/video-jobs/${jobId}`),

  connectSocial: (brandId: string, platform: string, oauthToken: string) =>
    request<{ platform: string; voice_analysis: Record<string, unknown> }>(
      `/api/brands/${brandId}/connect-social`,
      { method: 'POST', body: JSON.stringify({ platform, oauth_token: oauthToken }) },
    ),

  uploadVideoForRepurpose: (brandId: string, formData: FormData) =>
    fetch(`/api/brands/${brandId}/video-repurpose`, { method: 'POST', body: formData }).then(
      async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: r.statusText }))
          throw new Error(err.detail || `HTTP ${r.status}`)
        }
        return r.json()
      }
    ),

  getVideoRepurposeJob: (jobId: string, brandId: string) =>
    request<{
      job_id: string
      status: string
      clips: unknown[]
      error?: string
    }>(`/api/video-repurpose-jobs/${jobId}?brand_id=${encodeURIComponent(brandId)}`),

  downloadCalendar: (brandId: string, planId: string) =>
    fetch(`/api/brands/${brandId}/plans/${planId}/calendar.ics`)
      .then(async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: r.statusText }))
          throw new Error(err.detail || `HTTP ${r.status}`)
        }
        const blob = await r.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'amplifi_content_plan.ics'
        a.click()
        URL.revokeObjectURL(url)
      }),

  emailCalendar: (brandId: string, planId: string, email: string) =>
    request(`/api/brands/${brandId}/plans/${planId}/calendar/email`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  // Notion integration
  getNotionAuthUrl: (brandId: string) =>
    request<{ auth_url: string }>(`/api/brands/${brandId}/integrations/notion/auth-url`),
  disconnectNotion: (brandId: string) =>
    request(`/api/brands/${brandId}/integrations/notion/disconnect`, { method: 'POST' }),
  getNotionDatabases: (brandId: string) =>
    request<{ databases: { id: string; title: string }[] }>(
      `/api/brands/${brandId}/integrations/notion/databases`,
    ),
  selectNotionDatabase: (brandId: string, databaseId: string, databaseName: string) =>
    request(`/api/brands/${brandId}/integrations/notion/select-database`, {
      method: 'POST',
      body: JSON.stringify({ database_id: databaseId, database_name: databaseName }),
    }),
  exportToNotion: (brandId: string, planId: string) =>
    request<{ exported: number; total: number; results: { post_id: string; status: string; error?: string }[] }>(
      `/api/brands/${brandId}/plans/${planId}/export/notion`,
      { method: 'POST' },
    ),
}
