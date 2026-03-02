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
  audioNote: string | null   // tip for video_first posts (add audio before publishing)
  postId: string | null
  error: string | null
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
    audioNote: null,
    postId: null,
    error: null,
  })

  const eventSourceRef = useRef<EventSource | null>(null)

  const generate = useCallback((planId: string, dayIndex: number, brandId: string, instructions?: string) => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
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
      audioNote: null,
      postId: null,
      error: null,
    })

    const instructionsParam = instructions ? `&instructions=${encodeURIComponent(instructions)}` : ''
    const url = `/api/generate/${planId}/${dayIndex}?brand_id=${encodeURIComponent(brandId)}${instructionsParam}`
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
      setState(prev => ({
        ...prev,
        status: 'complete',
        postId: data.post_id,
        caption: data.caption || prev.caption,
        hashtags: data.hashtags || prev.hashtags,
        imageUrl: data.image_url || prev.imageUrl,
        imageUrls: data.image_urls?.length ? data.image_urls : prev.imageUrls,
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
      }))
      es.close()
    })

    es.addEventListener('error', (e: MessageEvent) => {
      // Check if this is a named 'error' SSE event (from our server) or a connection error
      if (e.data) {
        const data = JSON.parse(e.data)
        setState(prev => ({ ...prev, status: 'error', error: data.message }))
      } else {
        // Natural connection close after stream ends — not an error if generation completed
        setState(prev => {
          if (prev.status === 'complete') return prev  // already done, ignore
          return { ...prev, status: 'error', error: 'Connection lost' }
        })
      }
      es.close()
    })

    return () => es.close()
  }, [])

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
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
      audioNote: null,
      postId: null,
      error: null,
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
      audioNote: null,
      postId: post.postId,
      error: null,
    })
  }, [])

  return { state, generate, reset, loadExisting }
}
