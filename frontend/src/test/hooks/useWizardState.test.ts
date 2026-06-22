import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import { useWizardState } from '../../hooks/useWizardState'

describe('useWizardState', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('initializes to step 1', () => {
    const { result } = renderHook(() => useWizardState())
    expect(result.current.step).toBe(1)
  })

  it('next() does not advance when canAdvance returns false (empty data)', () => {
    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.next()
    })

    // step 1 requires businessName + description >= 20 chars
    expect(result.current.step).toBe(1)
  })

  it('next() advances step when canAdvance returns true', () => {
    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.update('businessName', 'Acme Corp')
      result.current.update('description', 'This is a description long enough to pass the check here')
    })

    act(() => {
      result.current.next()
    })

    expect(result.current.step).toBe(2)
  })

  it('back() decrements step', () => {
    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.update('businessName', 'Acme Corp')
      result.current.update('description', 'This is a description long enough to pass the check here')
    })

    act(() => {
      result.current.next()
    })

    expect(result.current.step).toBe(2)

    act(() => {
      result.current.back()
    })

    expect(result.current.step).toBe(1)
  })

  it('persists to sessionStorage on state change', () => {
    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.update('businessName', 'Stored Brand')
    })

    const stored = JSON.parse(sessionStorage.getItem('amplifi_wizard') || '{}')
    expect(stored.data.businessName).toBe('Stored Brand')
  })

  it('restores from sessionStorage on remount', () => {
    // Seed sessionStorage first
    sessionStorage.setItem(
      'amplifi_wizard',
      JSON.stringify({ step: 2, data: { businessName: 'Restored', description: '' } })
    )

    const { result } = renderHook(() => useWizardState())

    expect(result.current.step).toBe(2)
    expect(result.current.data.businessName).toBe('Restored')
  })

  it('clear() removes sessionStorage entry', () => {
    sessionStorage.setItem('amplifi_wizard', JSON.stringify({ step: 1, data: {} }))

    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.clear()
    })

    expect(sessionStorage.getItem('amplifi_wizard')).toBeNull()
  })

  it('handles corrupt sessionStorage gracefully (JSON parse error)', () => {
    sessionStorage.setItem('amplifi_wizard', 'invalid json {{{')

    // Should not throw — falls back to initial state
    const { result } = renderHook(() => useWizardState())
    expect(result.current.step).toBe(1)
  })

  it('canAdvance returns true for step 2 (default branch)', () => {
    const { result } = renderHook(() => useWizardState())

    // canAdvance at step 2 hits the default: return true branch
    expect(result.current.canAdvance(2)).toBe(true)
    expect(result.current.canAdvance(3)).toBe(true)
  })

  it('next() at step 3 does not advance beyond 3', () => {
    const { result } = renderHook(() => useWizardState())

    // Advance to step 3
    act(() => {
      result.current.update('businessName', 'Acme')
      result.current.update('description', 'A description long enough to advance step one')
    })
    act(() => { result.current.next() }) // step 2
    act(() => { result.current.next() }) // step 3
    act(() => { result.current.next() }) // should stay at 3

    expect(result.current.step).toBe(3)
  })

  it('back() at step 1 does not go below 1', () => {
    const { result } = renderHook(() => useWizardState())

    act(() => {
      result.current.back()
    })

    expect(result.current.step).toBe(1)
  })
})
