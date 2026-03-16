import { useState, useRef, useCallback, type MutableRefObject } from 'react'
import { getFreshIdToken } from '../api/firebase'

export type VoiceCoachStatus = 'idle' | 'connecting' | 'active' | 'error'

interface UseVoiceCoachResult {
  status: VoiceCoachStatus
  isAISpeaking: boolean
  transcript: string | null
  error: string | null
  startSession: (brandId: string, planId?: string) => Promise<void>
  stopSession: () => void
}

// AudioWorklet processor — inlined as a blob; no separate file needed.
// Uses the global `sampleRate` (AudioContext's actual rate) to downsample to 16kHz,
// so the resampling works correctly regardless of the OS audio device rate.
const WORKLET_SRC = `
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    // sampleRate is a global in AudioWorkletGlobalScope = AudioContext.sampleRate
    this._ratio = sampleRate / 16000
    this._phase = 0
  }
  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel || channel.length === 0) return true

    const ratio = this._ratio
    const outputLength = Math.floor((channel.length - this._phase) / ratio)
    if (outputLength <= 0) {
      this._phase -= channel.length
      return true
    }

    const pcm = new Int16Array(outputLength)
    for (let i = 0; i < outputLength; i++) {
      const srcIdx = this._phase + i * ratio
      const lo = Math.floor(srcIdx)
      const hi = Math.min(lo + 1, channel.length - 1)
      const frac = srcIdx - lo
      const sample = channel[lo] * (1 - frac) + channel[hi] * frac
      const s = Math.max(-1, Math.min(1, sample))
      pcm[i] = s < 0 ? s * 32768 : s * 32767
    }
    this._phase = (this._phase + outputLength * ratio) - channel.length
    this.port.postMessage(pcm.buffer, [pcm.buffer])
    return true
  }
}
registerProcessor('pcm-processor', PCMProcessor)
`

// Max reconnect attempts before giving up
const MAX_RECONNECTS = 5

export function useVoiceCoach(): UseVoiceCoachResult {
  const [status, setStatus] = useState<VoiceCoachStatus>('idle')
  const [isAISpeaking, setIsAISpeaking] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const captureCtxRef = useRef<AudioContext | null>(null)
  const playbackCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const playNextTimeRef = useRef<number>(0)
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const aiSpeakingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Track whether session ended gracefully (prevents onclose from showing error)
  const gracefulEndRef = useRef(false)
  // CRIT-4: synchronous guard to prevent double-tap launching two sessions
  const isStartingRef = useRef(false)
  // Conversation history for multi-turn continuity
  const conversationHistoryRef = useRef<string[]>([])
  const brandIdRef = useRef<string>('')
  const planIdRef = useRef<string | undefined>(undefined)
  const reconnectCountRef = useRef(0)
  // Flag to distinguish user-initiated stop from auto-reconnect teardown
  const userStoppedRef = useRef(false)

  // Tear down WebSocket + audio only (keep mic stream for reconnect)
  const teardownConnection = useCallback(() => {
    const ws = wsRef.current
    wsRef.current = null
    if (ws) ws.close()

    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect()
      sourceNodeRef.current = null
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect()
      workletNodeRef.current = null
    }
    if (captureCtxRef.current) {
      captureCtxRef.current.close().catch(() => {})
      captureCtxRef.current = null
    }
    if (playbackCtxRef.current) {
      playbackCtxRef.current.close().catch(() => {})
      playbackCtxRef.current = null
    }
    if (aiSpeakingTimerRef.current) {
      clearTimeout(aiSpeakingTimerRef.current)
      aiSpeakingTimerRef.current = null
    }
    playNextTimeRef.current = 0
    setIsAISpeaking(false)
  }, [])

  // Full teardown: connection + mic stream + reset all state
  const stopSession = useCallback(() => {
    userStoppedRef.current = true
    teardownConnection()

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }

    isStartingRef.current = false
    gracefulEndRef.current = false
    reconnectCountRef.current = 0
    conversationHistoryRef.current = []
    brandIdRef.current = ''
    setTranscript(null)
    setStatus('idle')
  }, [teardownConnection])

  // Wire up a WebSocket to a given mic stream + audio contexts
  const connectWebSocket = useCallback(async (
    brandId: string,
    stream: MediaStream,
    contextStr: string,
    planId?: string,
  ) => {
    gracefulEndRef.current = false
    userStoppedRef.current = false

    // Fresh audio contexts for each connection
    const captureCtx = new AudioContext()
    captureCtxRef.current = captureCtx
    const playbackCtx = new AudioContext({ sampleRate: 24000 })
    playbackCtxRef.current = playbackCtx
    playNextTimeRef.current = playbackCtx.currentTime

    // Get fresh Firebase ID token for WebSocket auth via Sec-WebSocket-Protocol.
    // forceRefresh ensures we don't send a near-expired cached token.
    // Token fetch MUST happen before WebSocket construction.
    const idToken = await getFreshIdToken()
    if (!idToken) {
      setError('Not authenticated. Please sign in and try again.')
      setStatus('error')
      stopSession()
      return
    }

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams()
    if (contextStr) params.set('context', contextStr)
    if (planId) params.set('plan_id', planId)
    const qs = params.toString() ? `?${params.toString()}` : ''
    const wsUrl = `${proto}://${window.location.host}/api/brands/${brandId}/voice-coaching${qs}`
    const ws = new WebSocket(wsUrl, [`auth.${idToken}`])
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onerror = () => {
      stopSession()
      setError('Connection failed. Check that the backend is running.')
      setStatus('error')
    }

    ws.onclose = () => {
      if (gracefulEndRef.current || userStoppedRef.current) {
        return
      }
      if (wsRef.current !== null) {
        stopSession()
        setError('Session ended unexpectedly.')
        setStatus('error')
      }
    }

    ws.onmessage = async (event) => {
      if (event.data instanceof ArrayBuffer) {
        const pCtx = playbackCtxRef.current
        if (pCtx && pCtx.state !== 'closed') {
          schedulePCMChunk(event.data, pCtx, playNextTimeRef)
        }
        setIsAISpeaking(true)
        if (aiSpeakingTimerRef.current) clearTimeout(aiSpeakingTimerRef.current)
        aiSpeakingTimerRef.current = setTimeout(() => setIsAISpeaking(false), 1200)
      } else {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'connected') {
            setStatus('active')
            try {
              await startMicCapture(captureCtx, stream, ws, workletNodeRef, sourceNodeRef)
            } catch (err: any) {
              setError(`Microphone setup failed: ${err.message}`)
              setStatus('error')
              stopSession()
            }
          } else if (msg.type === 'turn_complete') {
            if (aiSpeakingTimerRef.current) clearTimeout(aiSpeakingTimerRef.current)
            setIsAISpeaking(false)
          } else if (msg.type === 'transcript') {
            const text = msg.text ?? ''
            if (text) {
              conversationHistoryRef.current.push(`AI: ${text}`)
            }
            setTranscript(text || null)
          } else if (msg.type === 'session_ended') {
            // Gemini session ended naturally — auto-reconnect
            gracefulEndRef.current = true
            teardownConnection()

            if (userStoppedRef.current) return

            if (reconnectCountRef.current >= MAX_RECONNECTS) {
              setTranscript('Session limit reached. Click Voice Coach to start a new conversation.')
              setStatus('idle')
              if (streamRef.current) {
                streamRef.current.getTracks().forEach(t => t.stop())
                streamRef.current = null
              }
              isStartingRef.current = false
              return
            }

            reconnectCountRef.current++
            setStatus('connecting')
            setTranscript('Continuing conversation...')

            // Brief pause then reconnect with conversation history
            setTimeout(() => {
              if (userStoppedRef.current || !streamRef.current) return
              const history = conversationHistoryRef.current.slice(-10).join('\n')
              connectWebSocket(brandId, streamRef.current!, history, planIdRef.current)
                .catch(err => {
                  setError(`Reconnect failed: ${err?.message || 'Unknown error'}`)
                  setStatus('error')
                })
            }, 500)
          } else if (msg.type === 'session_complete') {
            // AI decided to end the conversation (user said goodbye etc.)
            gracefulEndRef.current = true
            stopSession()
            setTranscript(msg.message || 'Session complete.')
          } else if (msg.type === 'error') {
            setError(msg.message || 'Voice session error')
            setStatus('error')
            stopSession()
          }
        } catch {
          // ignore malformed control messages
        }
      }
    }
  }, [teardownConnection, stopSession])

  const startSession = useCallback(async (brandId: string, planId?: string) => {
    if (isStartingRef.current) return
    if (status !== 'idle' && status !== 'error') return
    isStartingRef.current = true
    userStoppedRef.current = false

    setError(null)
    setTranscript(null)
    setStatus('connecting')

    // Reset conversation state for fresh session
    conversationHistoryRef.current = []
    reconnectCountRef.current = 0
    brandIdRef.current = brandId
    planIdRef.current = planId

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    } catch (err: any) {
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone permission denied. Please allow microphone access and try again.'
        : `Microphone error: ${err.message}`
      setError(msg)
      setStatus('error')
      isStartingRef.current = false
      return
    }
    streamRef.current = stream

    await connectWebSocket(brandId, stream, '', planId)
  }, [status, connectWebSocket])

  return { status, isAISpeaking, transcript, error, startSession, stopSession }
}

// ── Audio helpers ──────────────────────────────────────────────────────────

async function startMicCapture(
  ctx: AudioContext,
  stream: MediaStream,
  ws: WebSocket,
  workletNodeRef: MutableRefObject<AudioWorkletNode | null>,
  sourceNodeRef: MutableRefObject<MediaStreamAudioSourceNode | null>,
) {
  const blob = new Blob([WORKLET_SRC], { type: 'application/javascript' })
  const blobUrl = URL.createObjectURL(blob)

  try {
    await ctx.audioWorklet.addModule(blobUrl)
  } finally {
    URL.revokeObjectURL(blobUrl)
  }

  const source = ctx.createMediaStreamSource(stream)
  sourceNodeRef.current = source

  const worklet = new AudioWorkletNode(ctx, 'pcm-processor')
  workletNodeRef.current = worklet

  worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(e.data)
    }
  }

  // Connect: source → worklet only (NOT to destination — prevents mic feedback)
  source.connect(worklet)
}

function schedulePCMChunk(
  buffer: ArrayBuffer,
  ctx: AudioContext,
  nextTimeRef: MutableRefObject<number>,
) {
  const int16 = new Int16Array(buffer)
  if (int16.length === 0) return

  const float32 = new Float32Array(int16.length)
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768
  }

  const audioBuffer = ctx.createBuffer(1, float32.length, ctx.sampleRate)
  audioBuffer.getChannelData(0).set(float32)

  const source = ctx.createBufferSource()
  source.buffer = audioBuffer
  source.connect(ctx.destination)

  const now = ctx.currentTime
  if (nextTimeRef.current < now) {
    nextTimeRef.current = now + 0.05
  }
  source.start(nextTimeRef.current)
  nextTimeRef.current += audioBuffer.duration
}
