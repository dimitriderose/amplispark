import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('../../api/client', () => import('../mocks/client'))

import { usePostLibrary } from '../../hooks/usePostLibrary'
import { api } from '../../api/client'

const mockPosts = [
  { post_id: 'p1', caption: 'Hello world', platform: 'instagram', status: 'complete', day_index: 0 },
  { post_id: 'p2', caption: 'Another post', platform: 'linkedin', status: 'approved', day_index: 1 },
]

describe('usePostLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches posts on mount when brandId is provided', async () => {
    vi.mocked(api.listPosts).mockResolvedValue({ posts: mockPosts } as never)

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(api.listPosts).toHaveBeenCalledWith('brand-123', undefined)
    expect(result.current.posts).toEqual(mockPosts)
  })

  it('returns empty array when brandId is empty string', async () => {
    const { result } = renderHook(() => usePostLibrary(''))

    await new Promise(r => setTimeout(r, 20))

    expect(api.listPosts).not.toHaveBeenCalled()
    expect(result.current.posts).toEqual([])
  })

  it('exposes loading state while fetching', async () => {
    vi.mocked(api.listPosts).mockReturnValue(new Promise(() => {}) as never)

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })
  })

  it('exposes error state when fetch fails', async () => {
    vi.mocked(api.listPosts).mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.posts).toEqual([])
  })

  it('refresh() re-fetches posts', async () => {
    vi.mocked(api.listPosts).mockResolvedValue({ posts: mockPosts } as never)

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(api.listPosts).toHaveBeenCalledTimes(1)

    vi.mocked(api.listPosts).mockResolvedValueOnce({ posts: [] } as never)

    act(() => {
      result.current.refresh()
    })

    await waitFor(() => {
      expect(api.listPosts).toHaveBeenCalledTimes(2)
    })
  })

  it('passes planId to api.listPosts when provided', async () => {
    vi.mocked(api.listPosts).mockResolvedValue({ posts: mockPosts } as never)

    const { result } = renderHook(() => usePostLibrary('brand-123', 'plan-456'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.listPosts).toHaveBeenCalledWith('brand-123', 'plan-456')
    expect(result.current.posts).toEqual(mockPosts)
  })

  it('returns empty array when api returns no posts field', async () => {
    vi.mocked(api.listPosts).mockResolvedValue({ posts: null } as never)

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.posts).toEqual([])
  })

  it('pollWhen condition is true when a post has generating status', async () => {
    const generatingPosts = [
      { post_id: 'p1', caption: 'Hello', platform: 'instagram', status: 'generating', day_index: 0 },
    ]
    vi.mocked(api.listPosts).mockResolvedValue({ posts: generatingPosts } as never)

    const { result } = renderHook(() => usePostLibrary('brand-123'))

    await waitFor(() => expect(result.current.loading).toBe(false))

    // Post with 'generating' status should be in the list
    expect(result.current.posts[0].status).toBe('generating')
  })

  it('polls again when posts contain a generating status (exercises pollWhen callback)', async () => {
    vi.useFakeTimers()
    const generatingPosts = [
      { post_id: 'p1', caption: 'Hello', platform: 'instagram', status: 'generating', day_index: 0 },
    ]
    vi.mocked(api.listPosts).mockResolvedValue({ posts: generatingPosts } as never)

    renderHook(() => usePostLibrary('brand-123'))

    await act(async () => {
      await Promise.resolve() // flush initial fetch
    })

    const callCountBefore = vi.mocked(api.listPosts).mock.calls.length

    // Advance timers past the 8000ms poll interval
    await act(async () => {
      vi.advanceTimersByTime(9000)
      await Promise.resolve()
    })

    // pollWhen returns true (posts has generating), so another fetch should have happened
    expect(vi.mocked(api.listPosts).mock.calls.length).toBeGreaterThan(callCountBefore)

    vi.useRealTimers()
  })
})
