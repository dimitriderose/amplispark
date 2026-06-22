import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useFetch } from '../../hooks/useFetch'

describe('useFetch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts with loading=true when fetcher is provided', async () => {
    // Use a never-resolving promise to observe the loading state
    const fetcher = vi.fn(() => new Promise<string>(() => {}))
    const { result } = renderHook(() => useFetch(fetcher))

    // loading should flip to true as soon as the fetch starts
    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })
  })

  it('sets data on successful resolution', async () => {
    const fetcher = vi.fn().mockResolvedValue({ name: 'hello' })
    const { result } = renderHook(() => useFetch(fetcher))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual({ name: 'hello' })
    expect(result.current.error).toBe('')
  })

  it('sets error string on rejected fetch', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useFetch(fetcher))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.data).toBeNull()
  })

  it('sets generic error string when rejected with non-Error value', async () => {
    const fetcher = vi.fn().mockRejectedValue('oops')
    const { result } = renderHook(() => useFetch(fetcher))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Fetch failed')
  })

  it('does not fetch when fetcher is null', async () => {
    const { result } = renderHook(() => useFetch(null))

    // Give a tick for any async activity
    await new Promise(r => setTimeout(r, 20))

    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBe('')
  })

  it('refresh() triggers a new fetch', async () => {
    const fetcher = vi.fn().mockResolvedValue('first')
    const { result } = renderHook(() => useFetch(fetcher))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetcher).toHaveBeenCalledTimes(1)

    fetcher.mockResolvedValueOnce('second')

    act(() => {
      result.current.refresh()
    })

    await waitFor(() => {
      expect(result.current.data).toBe('second')
    })

    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('discards stale result when newer fetch completes first (sequence counter)', async () => {
    let resolveFirst!: (v: string) => void
    let resolveSecond!: (v: string) => void

    const fetcher = vi.fn()
      .mockImplementationOnce(() => new Promise<string>(res => { resolveFirst = res }))
      .mockImplementationOnce(() => new Promise<string>(res => { resolveSecond = res }))

    const { result } = renderHook(() => useFetch(fetcher))

    // Wait for first fetch to start (loading = true)
    await waitFor(() => expect(result.current.loading).toBe(true))

    // Trigger a second fetch before the first completes
    act(() => { result.current.refresh() })

    // Resolve second fetch first with 'second'
    act(() => { resolveSecond('second') })
    await waitFor(() => expect(result.current.data).toBe('second'))

    // Now resolve first fetch with 'stale' — should be discarded
    act(() => { resolveFirst('stale') })
    await new Promise(r => setTimeout(r, 20))

    // Data should still be 'second', not 'stale'
    expect(result.current.data).toBe('second')
  })

  it('polls on interval when pollMs is provided and pollWhen returns true', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue('data')

    renderHook(() => useFetch(fetcher, [], {
      pollMs: 5000,
      pollWhen: () => true,
    }))

    await act(async () => { await Promise.resolve() })
    const callsBefore = fetcher.mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(6000)
      await Promise.resolve()
    })

    expect(fetcher.mock.calls.length).toBeGreaterThan(callsBefore)
    vi.useRealTimers()
  })

  it('skips poll when pollWhen returns false', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue('data')

    renderHook(() => useFetch(fetcher, [], {
      pollMs: 5000,
      pollWhen: () => false,
    }))

    await act(async () => { await Promise.resolve() })
    const callsBefore = fetcher.mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(6000)
      await Promise.resolve()
    })

    // pollWhen returns false so no additional poll should have happened
    expect(fetcher.mock.calls.length).toBe(callsBefore)
    vi.useRealTimers()
  })

  it('polls without pollWhen (defaults to always poll)', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue('data')

    renderHook(() => useFetch(fetcher, [], { pollMs: 5000 }))

    await act(async () => { await Promise.resolve() })
    const callsBefore = fetcher.mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(6000)
      await Promise.resolve()
    })

    expect(fetcher.mock.calls.length).toBeGreaterThan(callsBefore)
    vi.useRealTimers()
  })
})
