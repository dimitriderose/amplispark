import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

let capturedCallback: ((user: unknown) => void) | null = null
const mockUnsubscribe = vi.fn()

vi.mock('../../api/firebase', () => ({
  auth: { currentUser: null },
  signInWithGoogle: vi.fn().mockResolvedValue({ uid: 'test-uid' }),
  signOutUser: vi.fn().mockResolvedValue(undefined),
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (user: unknown) => void) => {
    capturedCallback = cb
    return mockUnsubscribe
  }),
}))

const { mockGetUser } = vi.hoisted(() => ({ mockGetUser: vi.fn() }))
vi.mock('../../api/client', () => ({
  api: { getUser: mockGetUser },
}))

import { useAuth } from '../../hooks/useAuth'
import { signInWithGoogle, signOutUser } from '../../api/firebase'

const baseUserData = {
  role: 'user' as const,
  beta_expires_at: null,
  quick_posts_this_month: 0,
  calendars_this_month: 0,
  days_remaining: null,
  quick_posts_limit: null,
  calendars_limit: null,
}

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedCallback = null
    mockUnsubscribe.mockReset()
    mockGetUser.mockResolvedValue(baseUserData)
  })

  it('starts with loading=true', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.loading).toBe(true)
  })

  it('sets uid and user when onAuthStateChanged fires with a user', async () => {
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({
        uid: 'user-123',
        displayName: 'Test User',
        email: 'test@example.com',
        photoURL: 'https://example.com/photo.jpg',
      })
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.uid).toBe('user-123')
    expect(result.current.user).toEqual({
      displayName: 'Test User',
      email: 'test@example.com',
      photoURL: 'https://example.com/photo.jpg',
    })
    expect(result.current.isSignedIn).toBe(true)
  })

  it('sets uid to null when onAuthStateChanged fires with null', async () => {
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!(null)
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.uid).toBeNull()
    expect(result.current.user).toBeNull()
    expect(result.current.isSignedIn).toBe(false)
  })

  it('signIn() calls signInWithGoogle', async () => {
    const { result } = renderHook(() => useAuth())

    await act(async () => {
      await result.current.signIn()
    })

    expect(signInWithGoogle).toHaveBeenCalledOnce()
  })

  it('signOut() calls signOutUser', async () => {
    const { result } = renderHook(() => useAuth())

    await act(async () => {
      await result.current.signOut()
    })

    expect(signOutUser).toHaveBeenCalledOnce()
  })

  it('calls the unsubscribe function returned by onAuthStateChanged on unmount', () => {
    const { unmount } = renderHook(() => useAuth())
    unmount()
    expect(mockUnsubscribe).toHaveBeenCalledOnce()
  })

  it('ignores auth state callback after component unmounts (isMounted guard)', async () => {
    const { result, unmount } = renderHook(() => useAuth())

    unmount()

    act(() => {
      capturedCallback!({
        uid: 'user-after-unmount',
        displayName: 'Ghost',
        email: 'ghost@example.com',
        photoURL: null,
      })
    })

    expect(result.current.uid).toBeNull()
  })

  it('sets role from getUser response', async () => {
    mockGetUser.mockResolvedValue({ ...baseUserData, role: 'beta' })
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.role).toBe('beta')
  })

  it('sets usageCounters from getUser response', async () => {
    mockGetUser.mockResolvedValue({
      ...baseUserData,
      role: 'beta',
      quick_posts_this_month: 2,
      calendars_this_month: 1,
      days_remaining: 20,
      quick_posts_limit: 8,
      calendars_limit: 4,
    })
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.usageCounters).toEqual({
      quickPostsThisMonth: 2,
      calendarsThisMonth: 1,
      daysRemaining: 20,
      quickPostsLimit: 8,
      calendarsLimit: 4,
    })
  })

  it('sets betaExpired when beta_expires_at is in the past', async () => {
    mockGetUser.mockResolvedValue({
      ...baseUserData,
      role: 'beta',
      beta_expires_at: new Date(Date.now() - 1000).toISOString(),
    })
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.betaExpired).toBe(true)
  })

  it('sets betaExpired false when beta_expires_at is in the future', async () => {
    mockGetUser.mockResolvedValue({
      ...baseUserData,
      role: 'beta',
      beta_expires_at: new Date(Date.now() + 86400000).toISOString(),
    })
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.betaExpired).toBe(false)
  })

  it('sets role null when getUser returns 404', async () => {
    mockGetUser.mockRejectedValue(new Error('404 Not Found'))
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.role).toBeNull()
    expect(result.current.userFetchError).toBe(false)
  })

  it('sets userFetchError true on non-404 getUser failure', async () => {
    mockGetUser.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.userFetchError).toBe(true)
  })

  it('signOut clears role and usageCounters', async () => {
    mockGetUser.mockResolvedValue({ ...baseUserData, role: 'user' })
    const { result } = renderHook(() => useAuth())

    act(() => {
      capturedCallback!({ uid: 'user-123', displayName: 'Alice', email: 'a@b.com', photoURL: null })
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.signOut()
    })

    expect(signOutUser).toHaveBeenCalledOnce()
    expect(result.current.uid).toBeNull()
    expect(result.current.role).toBeNull()
    expect(result.current.usageCounters).toBeNull()
  })
})
