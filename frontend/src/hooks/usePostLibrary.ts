import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import type { Post } from '../types'

export type { Post } from '../types'

export function usePostLibrary(brandId: string, planId?: string) {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // Ref so polling interval can read latest posts without being a dep (avoids
  // restarting the interval—and resetting its timer—on every fetch response)
  const postsRef = useRef(posts)
  postsRef.current = posts

  const fetch = useCallback(async () => {
    if (!brandId) return
    setLoading(true)
    setError('')
    try {
      const res = await api.listPosts(brandId, planId) as { posts: Post[] }
      setPosts(res.posts || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load posts')
    } finally {
      setLoading(false)
    }
  }, [brandId, planId])

  useEffect(() => { fetch() }, [fetch])

  // H-7: Auto-refresh every 8 seconds when any post is still generating.
  // Use postsRef so the interval is stable and doesn't restart on every response.
  useEffect(() => {
    const interval = setInterval(() => {
      if (postsRef.current.some(p => p.status === 'generating')) fetch()
    }, 8000)
    return () => clearInterval(interval)
  }, [fetch])

  return { posts, loading, error, refresh: fetch }
}
