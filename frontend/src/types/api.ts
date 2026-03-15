import type { BrandProfile, Post, Plan } from '.'

export interface BrandResponse {
  brand_profile: BrandProfile
}

export interface CreateBrandResponse {
  brand_id: string
  status: string
}

export interface BrandsListResponse {
  brands: (BrandProfile & { brand_id: string })[]
}

export interface PostsListResponse {
  posts: Post[]
}

export interface PlansListResponse {
  plans: Plan[]
}

export interface PlanResponse {
  plan_profile: Plan
}

export interface CreatePlanResponse {
  plan_id: string
  status: string
  days: unknown[]
  trend_summary: Record<string, unknown>
}

export interface PostResponse extends Post {}

export interface UpdatePostResponse {
  post: Post
}

export interface ReviewPostResponse {
  review: Record<string, unknown>
  post_id: string
}

export interface ApprovePostResponse {
  status: string
  post_id: string
}

export interface RegenerateResponse {
  generate_url: string
}

export interface UploadAssetResponse {
  uploaded: { url: string; filename: string; type: string }[]
}

export interface DayPhotoResponse {
  custom_photo_url: string
}

export interface VideoJobResponse {
  job_id: string
  status: string
  video_url?: string
  error?: string
}

export interface EditMediaResponse {
  image_url?: string
  video_url?: string
  edit_count?: number
}

export interface ResetMediaResponse {
  image_url?: string
}

export interface RefreshResearchResponse {
  trend_summary: Record<string, unknown>
}
