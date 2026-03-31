import { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api/client'

type VideoStatus = 'idle' | 'generating' | 'complete' | 'error'

export function useVideoGeneration(postId: string, brandId: string, existingVideoUrl?: string | null) {
  const [status, setStatus] = useState<VideoStatus>(existingVideoUrl ? 'complete' : 'idle')
  const [videoUrl, setVideoUrl] = useState<string | null>(existingVideoUrl ?? null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // H8/M20: Guard against duplicate submissions
  const isGeneratingRef = useRef(false)

  const startGeneration = useCallback(
    async (tier: 'fast' | 'standard' = 'fast') => {
      if (isGeneratingRef.current) return
      isGeneratingRef.current = true
      setStatus('generating')
      setProgress(0)
      setError('')

      try {
        const res = (await api.generateVideo(postId, tier, brandId)) as any
        const { job_id, estimated_seconds } = res
        const startTime = Date.now()
        const MAX_POLL_MS = 25 * 60 * 1000 // 25 minutes

        intervalRef.current = setInterval(async () => {
          if (Date.now() - startTime > MAX_POLL_MS) {
            clearInterval(intervalRef.current!)
            isGeneratingRef.current = false
            setError('Video generation timed out. Please try again.')
            setStatus('error')
            return
          }
          try {
            const job = (await api.getVideoJob(job_id)) as any
            const elapsed = (Date.now() - startTime) / 1000
            setProgress(Math.min(95, (elapsed / (estimated_seconds || 150)) * 100))

            if (job.status === 'complete') {
              clearInterval(intervalRef.current!)
              isGeneratingRef.current = false
              setVideoUrl(job.result?.video_url || null)
              setProgress(100)
              setStatus('complete')
            } else if (job.status === 'failed') {
              clearInterval(intervalRef.current!)
              isGeneratingRef.current = false
              setError(job.result?.error || 'Video generation failed')
              setStatus('error')
            }
          } catch {
            // keep polling — transient network errors are expected
          }
        }, 5000)
      } catch (err: any) {
        isGeneratingRef.current = false
        setError(err.message || 'Failed to start video generation')
        setStatus('error')
      }
    },
    [postId, brandId]
  )

  // Reset state when postId or existingVideoUrl changes (navigating between posts)
  useEffect(() => {
    // Clear any in-flight polling from the previous post
    isGeneratingRef.current = false
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (existingVideoUrl) {
      setStatus('complete')
      setVideoUrl(existingVideoUrl)
      setProgress(100)
      setError('')
    } else {
      setStatus('idle')
      setVideoUrl(null)
      setProgress(0)
      setError('')
    }
  }, [postId, existingVideoUrl])

  // Clear interval on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  return { status, videoUrl, progress, error, startGeneration }
}
