import { useState, useEffect, useCallback, useRef } from 'react'

export interface UseFetchResult<T> {
  data: T | null
  loading: boolean
  error: string
  refresh: () => void
}

export function useFetch<T>(
  fetcher: (() => Promise<T>) | null,
  deps: unknown[] = [],
  options?: {
    pollMs?: number
    pollWhen?: (data: T | null) => boolean
  }
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const dataRef = useRef<T | null>(null)
  dataRef.current = data

  // Store fetcher and pollWhen in refs to avoid stale closures and dep instability
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const pollWhenRef = useRef(options?.pollWhen)
  pollWhenRef.current = options?.pollWhen

  // Request sequence counter to prevent stale data from overwriting fresh data
  const seqRef = useRef(0)
  const loadingRef = useRef(false)

  const doFetch = useCallback(async () => {
    const fn = fetcherRef.current
    if (!fn) return
    const seq = ++seqRef.current
    setLoading(true)
    loadingRef.current = true
    setError('')
    try {
      const result = await fn()
      // Only apply if this is still the latest request
      if (seq === seqRef.current) {
        setData(result)
      }
    } catch (e: unknown) {
      if (seq === seqRef.current) {
        setError(e instanceof Error ? e.message : 'Fetch failed')
      }
    } finally {
      if (seq === seqRef.current) {
        setLoading(false)
        loadingRef.current = false
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    doFetch()
  }, [doFetch])

  // Polling support — refs prevent interval restarts on every render
  useEffect(() => {
    if (!options?.pollMs) return
    const interval = setInterval(() => {
      if (loadingRef.current) return // skip if fetch already in flight
      const shouldPoll = pollWhenRef.current ? pollWhenRef.current(dataRef.current) : true
      if (shouldPoll) doFetch()
    }, options.pollMs)
    return () => clearInterval(interval)
  }, [doFetch, options?.pollMs])

  return { data, loading, error, refresh: doFetch }
}
