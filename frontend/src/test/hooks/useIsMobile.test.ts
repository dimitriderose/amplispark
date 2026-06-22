import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, afterEach } from 'vitest'

import { useIsMobile } from '../../hooks/useIsMobile'

type MediaQueryCallback = (e: MediaQueryListEvent) => void

function mockMatchMedia(matches: boolean) {
  const listeners: MediaQueryCallback[] = []
  const mql = {
    matches,
    addEventListener: vi.fn((_: string, cb: MediaQueryCallback) => listeners.push(cb)),
    removeEventListener: vi.fn(),
    // expose for manual triggering in tests
    _listeners: listeners,
  }
  window.matchMedia = vi.fn().mockReturnValue(mql)
  return mql
}

describe('useIsMobile', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns true when window.innerWidth matches (max-width: 640px)', () => {
    mockMatchMedia(true)

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(true)
  })

  it('returns false for desktop width', () => {
    mockMatchMedia(false)

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(false)
  })

  it('updates on window resize event (change event)', () => {
    const mql = mockMatchMedia(false)

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(false)

    act(() => {
      mql._listeners.forEach(cb => cb({ matches: true } as MediaQueryListEvent))
    })

    expect(result.current).toBe(true)
  })

  it('removes event listener on unmount', () => {
    const mql = mockMatchMedia(false)

    const { unmount } = renderHook(() => useIsMobile())
    unmount()

    expect(mql.removeEventListener).toHaveBeenCalled()
  })
})

import { useIsTablet, useIsSmallScreen } from '../../hooks/useIsMobile'

describe('useIsTablet', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns true when matchMedia matches tablet range', () => {
    mockMatchMedia(true)
    const { result } = renderHook(() => useIsTablet())
    expect(result.current).toBe(true)
  })

  it('returns false when matchMedia does not match tablet range', () => {
    mockMatchMedia(false)
    const { result } = renderHook(() => useIsTablet())
    expect(result.current).toBe(false)
  })

  it('updates on change event', () => {
    const mql = mockMatchMedia(false)
    const { result } = renderHook(() => useIsTablet())
    expect(result.current).toBe(false)

    act(() => {
      mql._listeners.forEach(cb => cb({ matches: true } as MediaQueryListEvent))
    })

    expect(result.current).toBe(true)
  })

  it('removes event listener on unmount', () => {
    const mql = mockMatchMedia(true)
    const { unmount } = renderHook(() => useIsTablet())
    unmount()
    expect(mql.removeEventListener).toHaveBeenCalled()
  })
})

describe('useIsSmallScreen', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns true when matchMedia matches small screen', () => {
    mockMatchMedia(true)
    const { result } = renderHook(() => useIsSmallScreen())
    expect(result.current).toBe(true)
  })

  it('returns false when matchMedia does not match', () => {
    mockMatchMedia(false)
    const { result } = renderHook(() => useIsSmallScreen())
    expect(result.current).toBe(false)
  })

  it('updates on change event', () => {
    const mql = mockMatchMedia(true)
    const { result } = renderHook(() => useIsSmallScreen())
    expect(result.current).toBe(true)

    act(() => {
      mql._listeners.forEach(cb => cb({ matches: false } as MediaQueryListEvent))
    })

    expect(result.current).toBe(false)
  })

  it('removes event listener on unmount', () => {
    const mql = mockMatchMedia(true)
    const { unmount } = renderHook(() => useIsSmallScreen())
    unmount()
    expect(mql.removeEventListener).toHaveBeenCalled()
  })
})

describe('useMediaQuery SSR guard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns false when window.matchMedia is not a function (SSR-like)', () => {
    // Simulate environment where matchMedia is not available
    const original = window.matchMedia
    Object.defineProperty(window, 'matchMedia', {
      value: undefined,
      writable: true,
      configurable: true,
    })

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)

    // Restore
    Object.defineProperty(window, 'matchMedia', {
      value: original,
      writable: true,
      configurable: true,
    })
  })
})
