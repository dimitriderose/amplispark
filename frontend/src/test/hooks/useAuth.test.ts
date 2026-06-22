import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// Capture the onAuthStateChanged callback so tests can invoke it
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

import { useAuth } from '../../hooks/useAuth'
import { signInWithGoogle, signOutUser } from '../../api/firebase'

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedCallback = null
    mockUnsubscribe.mockReset()
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

    // Unmount before the callback fires
    unmount()

    // Fire the callback after unmount — should be ignored (isMounted = false)
    act(() => {
      capturedCallback!({
        uid: 'user-after-unmount',
        displayName: 'Ghost',
        email: 'ghost@example.com',
        photoURL: null,
      })
    })

    // After unmount, result.current should still be the initial state
    expect(result.current.uid).toBeNull()
  })
})
