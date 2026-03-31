import { useState, useRef, useCallback } from 'react'

export type GenerationStatus = 'idle' | 'generating' | 'complete' | 'error'

export interface GenerationState {
  status: GenerationStatus
  statusMessage: string
  captionChunks: string[]    // streaming caption text pieces
  caption: string            // final complete caption
  hashtags: string[]
  imageUrl: string | null
  imageUrls: string[]        // carousel: all slide URLs
  videoUrl: string | null
  videoGenerating: boolean   // true while backend auto-generates Veo video
  audioNote: string | null   // tip for video_first posts (add audio before publishing)
  postId: string | null
  error: string | null
  review: Record<string, any> | null  // inline review from review gate
}

export function usePostGeneration() {
  const [state, setState] = useState<GenerationState>({
    status: 'idle',
    statusMessage: '',
    captionChunks: [],
    caption: '',
    hashtags: [],
    imageUrl: null,
    imageUrls: [],
    videoUrl: null,
    videoGenerating: false,
    audioNote: null,
    postId: null,
    error: null,
    review: null,
  })

  const eventSourceRef = useRef<EventSource | null>(null)
  // M20: Prevent duplicate submissions
  const isSubmittingRef = useRef(false)

  const generate = useCallback((planId: string, dayIndex: number, brandId: string, instructions?: string, imageStyle?: string) => {
    // M20: Guard against rapid duplicate calls
    if (isSubmittingRef.current) return () => {}
    isSubmittingRef.current = true

    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    setState({
      status: 'generating',
      statusMessage: 'Starting generation...',
      captionChunks: [],
      caption: '',
      hashtags: [],
      imageUrl: null,
      imageUrls: [],
      videoUrl: null,
      videoGenerating: false,
      audioNote: null,
      postId: null,
      error: null,
      review: null,
    })

    // M21: Wrap EventSource initialization in try/catch
    try {
      const instructionsParam = instructions ? `&instructions=${encodeURIComponent(instructions)}` : ''
      const imageStyleParam = imageStyle ? `&image_style=${encodeURIComponent(imageStyle)}` : ''
      const url = `/api/generate/${planId}/${dayIndex}?brand_id=${encodeURIComponent(brandId)}${instructionsParam}${imageStyleParam}`
      const es = new EventSource(url)
      eventSourceRef.current = es

      es.addEventListener('status', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        setState(prev => ({ ...prev, statusMessage: data.message }))
      })

      es.addEventListener('caption', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        if (data.chunk) {
          setState(prev => ({
            ...prev,
            captionChunks: [...prev.captionChunks, data.text],
          }))
        } else {
          setState(prev => ({
            ...prev,
            caption: data.text,
            hashtags: data.hashtags || [],
            captionChunks: [],
          }))
        }
      })

      es.addEventListener('image', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        setState(prev => ({
          ...prev,
          imageUrl: prev.imageUrl || data.url,  // first image becomes primary
          imageUrls: [...prev.imageUrls, data.url],
        }))
      })

      es.addEventListener('complete', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        isSubmittingRef.current = false
        setState(prev => ({
          ...prev,
          status: 'complete',
          postId: data.post_id,
          caption: data.caption || prev.caption,
          hashtags: data.hashtags || prev.hashtags,
          imageUrl: data.image_url || prev.imageUrl,
          imageUrls: data.image_urls?.length ? data.image_urls : prev.imageUrls,
          review: data.review || null,
          videoGenerating: data.awaiting_video || false,
        }))
        // Don't close here — video_first posts have more events coming.
        // The ES closes on video_complete, video_error, or natural connection end.
      })

      es.addEventListener('video_complete', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        setState(prev => ({
          ...prev,
          videoUrl: data.video_url,
          audioNote: data.audio_note || null,
          statusMessage: '',
          videoGenerating: false,
        }))
        es.close()
      })

      es.addEventListener('video_error', (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        // Video failed but we still have the caption — keep status as 'complete'
        setState(prev => ({
          ...prev,
          statusMessage: '',
          audioNote: `Video generation failed: ${data.message}. Use the "Generate Video" button to retry.`,
          videoGenerating: false,
        }))
        es.close()
      })

      // Named 'error' SSE event from our server (e.g., generation logic failed)
      es.addEventListener('error', (e: MessageEvent) => {
        if (e.data) {
          const data = JSON.parse(e.data)
          isSubmittingRef.current = false
          setState(prev => ({ ...prev, status: 'error', error: data.message }))
          es.close()
        }
      })

      // Browser-level connection error (backend down, network drop, proxy timeout)
      es.onerror = () => {
        isSubmittingRef.current = false
        setState(prev => {
          if (prev.status === 'complete') {
            // Connection dropped after completion — clear video flag so manual button shows
            return prev.videoGenerating ? { ...prev, videoGenerating: false } : prev
          }
          return { ...prev, status: 'error', error: 'Connection lost — the server may have restarted. Click "Regenerate" to try again.' }
        })
        es.close()
      }
    } catch (err: unknown) {
      // M21: Handle failure before EventSource connects (e.g. invalid URL, network down)
      isSubmittingRef.current = false
      const message = err instanceof Error ? err.message : 'Failed to start generation'
      setState(prev => ({ ...prev, status: 'error', error: message }))
    }

    // M19: Return cleanup function that closes EventSource on unmount
    return () => {
      isSubmittingRef.current = false
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [])

  const reset = useCallback(() => {
    isSubmittingRef.current = false
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setState({
      status: 'idle',
      statusMessage: '',
      captionChunks: [],
      caption: '',
      hashtags: [],
      imageUrl: null,
      imageUrls: [],
      videoUrl: null,
      videoGenerating: false,
      audioNote: null,
      postId: null,
      error: null,
      review: null,
    })
  }, [])

  /** Load an already-generated post into the state (view mode). */
  const loadExisting = useCallback((post: {
    postId: string
    caption: string
    hashtags: string[]
    imageUrl: string | null
    imageUrls?: string[]
    videoUrl?: string | null
  }) => {
    setState({
      status: 'complete',
      statusMessage: '',
      captionChunks: [],
      caption: post.caption,
      hashtags: post.hashtags,
      imageUrl: post.imageUrl,
      imageUrls: post.imageUrls || (post.imageUrl ? [post.imageUrl] : []),
      videoUrl: post.videoUrl ?? null,
      videoGenerating: false,
      audioNote: null,
      postId: post.postId,
      error: null,
      review: null,
    })
  }, [])

  return { state, generate, reset, loadExisting }
}
