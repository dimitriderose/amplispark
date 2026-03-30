import { getIdToken, getUid } from './firebase'
import { downloadBlob } from '../utils/downloads'
import type {
  BrandResponse,
  CreateBrandResponse,
  BrandsListResponse,
  PostsListResponse,
  PlansListResponse,
  PlanResponse,
  CreatePlanResponse,
  PostResponse,
  UpdatePostResponse,
  ReviewPostResponse,
  ApprovePostResponse,
  RegenerateResponse,
  UploadAssetResponse,
  DayPhotoResponse,
  VideoJobResponse,
  EditMediaResponse,
  ResetMediaResponse,
  RefreshResearchResponse,
} from '../types/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const clone = res.clone()
    const err = await res.json().catch(async () => {
      const text = await clone.text().catch(() => '')
      return { error: text.slice(0, 200) || res.statusText }
    })
    throw new Error(err.detail || err.error || `HTTP ${res.status}`)
  }
  // Handle empty responses (204 No Content, empty body)
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T
  }
  return res.json()
}

async function handleBlobResponse(res: Response): Promise<Blob> {
  if (!res.ok) {
    const err = await res.json().catch(async () => {
      const text = await res.text().catch(() => '')
      return { error: text.slice(0, 200) || res.statusText }
    })
    throw new Error(err.detail || err.error || `HTTP ${res.status}`)
  }
  return res.blob()
}

async function _authHeaders(): Promise<Record<string, string>> {
  const token = await getIdToken()
  if (token) return { 'Authorization': `Bearer ${token}` }
  // Fallback to UID header during migration
  const uid = getUid()
  return uid ? { 'X-User-UID': uid } : {}
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const authH = await _authHeaders()
  const res = await fetch(path, {
    headers: {
      ...authH,
      ...(options?.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...options?.headers,
    },
    ...options,
  })
  return handleResponse<T>(res)
}

export const api = {
  listBrands: (ownerUid: string) =>
    request<BrandsListResponse>(`/api/brands?owner_uid=${encodeURIComponent(ownerUid)}`),
  createBrand: (data: object) =>
    request<CreateBrandResponse>('/api/brands', { method: 'POST', body: JSON.stringify(data) }),
  analyzeBrand: (brandId: string, data: object) =>
    request<BrandResponse>(`/api/brands/${brandId}/analyze`, { method: 'POST', body: JSON.stringify(data) }),
  getBrand: (brandId: string) => request<BrandResponse>(`/api/brands/${brandId}`),
  updateBrand: (brandId: string, data: object) =>
    request<BrandResponse>(`/api/brands/${brandId}`, { method: 'PUT', body: JSON.stringify(data) }),
  uploadBrandAsset: async (brandId: string, formData: FormData) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/upload`, {
      method: 'POST',
      headers: { ...('Authorization' in authH ? { Authorization: authH.Authorization } : authH) },
      body: formData,
    }).then(r => handleResponse<UploadAssetResponse>(r))
  },
  deleteBrandAsset: (brandId: string, assetIndex: number) =>
    request<void>(`/api/brands/${brandId}/assets/${assetIndex}`, { method: 'DELETE' }),
  setBrandLogo: (brandId: string, logoUrl: string | null) =>
    request<BrandResponse>(`/api/brands/${brandId}/logo`, {
      method: 'PATCH',
      body: JSON.stringify({ logo_url: logoUrl }),
    }),

  listPlans: (brandId: string) => request<PlansListResponse>(`/api/brands/${brandId}/plans`),
  createPlan: (brandId: string, numDays = 7, businessEvents?: string, platforms?: string[]) =>
    request<CreatePlanResponse>(`/api/brands/${brandId}/plans`, {
      method: 'POST',
      body: JSON.stringify({
        num_days: numDays,
        business_events: businessEvents || null,
        ...(platforms && platforms.length > 0 ? { platforms } : {}),
      }),
    }),
  getPlan: (brandId: string, planId: string) => request<PlanResponse>(`/api/brands/${brandId}/plans/${planId}`),
  updateDay: (brandId: string, planId: string, dayIndex: number, data: object) =>
    request<PlanResponse>(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}`, { method: 'PUT', body: JSON.stringify(data) }),

  listPosts: (brandId: string, planId?: string) =>
    request<PostsListResponse>(`/api/posts?brand_id=${brandId}${planId ? `&plan_id=${planId}` : ''}`),
  getPost: (brandId: string, postId: string) =>
    request<PostResponse>(`/api/posts/${postId}?brand_id=${brandId}`),
  updatePost: (brandId: string, postId: string, data: { caption?: string; hashtags?: string[] }) =>
    request<UpdatePostResponse>(`/api/brands/${brandId}/posts/${postId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  reviewPost: (brandId: string, postId: string, force = false) =>
    request<ReviewPostResponse>(`/api/brands/${brandId}/posts/${postId}/review${force ? '?force=true' : ''}`, { method: 'POST' }),
  approvePost: (brandId: string, postId: string) =>
    request<ApprovePostResponse>(`/api/brands/${brandId}/posts/${postId}/approve`, { method: 'POST' }),
  exportPost: async (postId: string, brandId: string) => {
    const authH = await _authHeaders()
    return fetch(`/api/posts/${postId}/export?brand_id=${encodeURIComponent(brandId)}`, {
      headers: { ...authH },
    })
      .then(r => handleBlobResponse(r))
      .then(async blob => {
        downloadBlob(blob, `amplifi_post_${postId}.zip`)
      })
  },
  exportPlan: async (planId: string, brandId: string) => {
    const authH = await _authHeaders()
    return fetch(`/api/export/${planId}?brand_id=${encodeURIComponent(brandId)}`, {
      method: 'POST',
      headers: { ...authH },
    })
      .then(r => handleBlobResponse(r))
      .then(blob => downloadBlob(blob, `amplifi_export_${planId}.zip`))
  },

  uploadDayPhoto: async (brandId: string, planId: string, dayIndex: number, formData: FormData) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}/photo`, {
      method: 'POST',
      headers: { ...('Authorization' in authH ? { Authorization: authH.Authorization } : authH) },
      body: formData,
    }).then(r => handleResponse<DayPhotoResponse>(r))
  },

  deleteDayPhoto: (brandId: string, planId: string, dayIndex: number) =>
    request<void>(`/api/brands/${brandId}/plans/${planId}/days/${dayIndex}/photo`, { method: 'DELETE' }),

  generateVideo: (postId: string, tier = 'fast', brandId = '') =>
    request<VideoJobResponse>(`/api/posts/${postId}/generate-video?tier=${tier}&brand_id=${brandId}`, { method: 'POST' }),
  getVideoJob: (jobId: string) => request<VideoJobResponse>(`/api/video-jobs/${jobId}`),

  connectSocial: (brandId: string, platform: string, oauthToken: string) =>
    request<{ platform: string; voice_analysis: Record<string, unknown> }>(
      `/api/brands/${brandId}/connect-social`,
      { method: 'POST', body: JSON.stringify({ platform, oauth_token: oauthToken }) },
    ),

  uploadVideoForRepurpose: async (brandId: string, formData: FormData) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/video-repurpose`, {
      method: 'POST',
      headers: { ...('Authorization' in authH ? { Authorization: authH.Authorization } : authH) },
      body: formData,
    }).then(r => handleResponse<{ job_id: string }>(r))
  },

  getVideoRepurposeJob: (jobId: string, brandId: string) =>
    request<{
      job_id: string
      status: string
      clips: unknown[]
      error?: string
    }>(`/api/video-repurpose-jobs/${jobId}?brand_id=${encodeURIComponent(brandId)}`),

  downloadCalendar: async (brandId: string, planId: string) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/plans/${planId}/calendar.ics`, {
      headers: { ...authH },
    })
      .then(r => handleBlobResponse(r))
      .then(blob => downloadBlob(blob, 'amplifi_content_plan.ics'))
  },

  emailCalendar: (brandId: string, planId: string, email: string) =>
    request<void>(`/api/brands/${brandId}/plans/${planId}/calendar/email`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  // Notion integration
  getNotionAuthUrl: (brandId: string) =>
    request<{ auth_url: string }>(`/api/brands/${brandId}/integrations/notion/auth-url`),
  disconnectNotion: (brandId: string) =>
    request<void>(`/api/brands/${brandId}/integrations/notion/disconnect`, { method: 'POST' }),
  getNotionDatabases: (brandId: string) =>
    request<{ databases: { id: string; title: string }[] }>(
      `/api/brands/${brandId}/integrations/notion/databases`,
    ),
  selectNotionDatabase: (brandId: string, databaseId: string, databaseName: string) =>
    request<void>(`/api/brands/${brandId}/integrations/notion/select-database`, {
      method: 'POST',
      body: JSON.stringify({ database_id: databaseId, database_name: databaseName }),
    }),
  exportToNotion: (brandId: string, planId: string) =>
    request<{ exported: number; total: number; results: { post_id: string; status: string; error?: string }[] }>(
      `/api/brands/${brandId}/plans/${planId}/export/notion`,
      { method: 'POST' },
    ),

  editPostMedia: async (brandId: string, postId: string, body: { edit_prompt: string; slide_index?: number; target?: string }) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/posts/${postId}/edit-media`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authH },
      body: JSON.stringify(body),
    }).then(r => handleResponse<EditMediaResponse>(r))
  },

  resetPostMedia: async (brandId: string, postId: string, target?: string) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/posts/${postId}/edit-media/reset${target ? `?target=${target}` : ''}`, {
      method: 'POST',
      headers: { ...authH },
    }).then(r => handleResponse<ResetMediaResponse>(r))
  },

  regeneratePost: (brandId: string, postId: string) =>
    request<RegenerateResponse>(`/api/brands/${brandId}/posts/${postId}/regenerate`, { method: 'POST' }),

  refreshPlanResearch: async (brandId: string, planId: string) => {
    const authH = await _authHeaders()
    return fetch(`/api/brands/${brandId}/plans/${planId}/refresh-research`, {
      method: 'POST',
      headers: { ...authH },
    }).then(r => handleResponse<RefreshResearchResponse>(r))
  },
}
