import { api } from '../api/client'
import type { Post } from '../types'
import { useFetch } from './useFetch'

export type { Post } from '../types'

export function usePostLibrary(brandId: string, planId?: string) {
  const { data, loading, error, refresh } = useFetch<Post[]>(
    brandId ? () => api.listPosts(brandId, planId).then(res => res.posts || []) : null,
    [brandId, planId],
    {
      pollMs: 8000,
      pollWhen: (posts) => posts?.some(p => p.status === 'generating') ?? false,
    }
  )

  return { posts: data || [], loading, error, refresh }
}
