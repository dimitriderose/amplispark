import { useEffect, useRef, useState } from 'react'
import { A } from '../theme'
import { api } from '../api/client'
import { getPlatform } from '../platformRegistry'

const SPIN_STYLE = `@keyframes vr-spin { to { transform: rotate(360deg); } }`
const PULSE_STYLE = `@keyframes vr-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }`

interface Clip {
  platform: string
  duration_seconds: number
  hook: string
  suggested_caption: string
  reason: string
  content_theme?: string
  clip_url: string | null
  filename: string
}

interface Job {
  job_id: string
  status: 'queued' | 'processing' | 'complete' | 'failed'
  clips: Clip[]
  error?: string
  filename?: string
}

const REPURPOSE_LABELS: Record<string, { label: string; platformKey: string }> = {
  reels:          { label: 'Instagram Reels', platformKey: 'instagram' },
  tiktok:         { label: 'TikTok',          platformKey: 'tiktok' },
  youtube_shorts: { label: 'YouTube Shorts',  platformKey: 'youtube_shorts' },
  linkedin:       { label: 'LinkedIn',        platformKey: 'linkedin' },
}

interface Props {
  brandId: string
}

export default function VideoRepurpose({ brandId }: Props) {
  const [job, setJob] = useState<Job | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const storageKey = `amplifi_vrjob_${brandId}`

  // startPolling is defined before the mount effect that calls it for readability
  const startPolling = (jobId: string) => {
    sessionStorage.setItem(storageKey, jobId)
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const j = await api.getVideoRepurposeJob(jobId, brandId) as Job
        setJob(j)
        if (j.status === 'complete' || j.status === 'failed') {
          clearInterval(pollRef.current!)
          pollRef.current = null
          sessionStorage.removeItem(storageKey)
        }
      } catch {
        // transient poll error — keep polling
      }
    }, 5000)
  }

  // M-7: Restore in-flight job from sessionStorage on mount (survives navigation).
  // brandId is stable for the component lifetime (routing unmounts on brand change),
  // so the empty dep array is intentional — storageKey and startPolling are stable closures.
  useEffect(() => {
    const savedJobId = sessionStorage.getItem(storageKey)
    if (savedJobId) {
      setJob({ job_id: savedJobId, status: 'processing', clips: [] })
      startPolling(savedJobId)
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const [selectedFileSize, setSelectedFileSize] = useState('')

  const handleFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['mp4', 'mov'].includes(ext ?? '')) {
      setError('Only .mp4 and .mov files are supported')
      return
    }
    setSelectedFileSize(formatFileSize(file.size))
    if (file.size > 500 * 1024 * 1024) {
      setError(`File is too large (${formatFileSize(file.size)}). Must be under 500 MB.`)
      return
    }

    setError('')
    setUploading(true)
    setJob(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.uploadVideoForRepurpose(brandId, formData) as { job_id: string; status: string }
      const newJob: Job = {
        job_id: res.job_id,
        status: 'queued',
        clips: [],
        filename: file.name,
      }
      setJob(newJob)
      startPolling(res.job_id)
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const isProcessing = job && (job.status === 'queued' || job.status === 'processing')
  const isDone = job?.status === 'complete'
  const isFailed = job?.status === 'failed'

  return (
    <div>
      <style>{SPIN_STYLE + PULSE_STYLE}</style>

      <div style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: A.text, margin: '0 0 4px' }}>
          Video Repurposing
        </h3>
        <p style={{ fontSize: 12, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
          Upload a raw video (mp4 / mov, up to 500 MB) and Amplispark will extract 2–3 platform-ready short clips.
        </p>
      </div>

      {/* Drop zone — hidden when a job is in progress or complete */}
      {!isProcessing && !isDone && (
        <div
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => !uploading && fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${dragOver ? A.violet : A.border}`,
            borderRadius: 10,
            padding: '20px 16px',
            textAlign: 'center',
            cursor: uploading ? 'not-allowed' : 'pointer',
            background: dragOver ? A.violetLight + '18' : A.surface,
            transition: 'border-color 0.2s, background 0.2s',
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp4,.mov,video/mp4,video/quicktime"
            style={{ display: 'none' }}
            onChange={handleInputChange}
          />
          {uploading ? (
            <>
              <div style={{
                width: 28, height: 28, borderRadius: '50%', margin: '0 auto 8px',
                border: `3px solid ${A.borderLight}`, borderTopColor: A.violet,
                animation: 'vr-spin 0.8s linear infinite',
              }} />
              <p style={{ fontSize: 12, color: A.textSoft, margin: 0 }}>Uploading{selectedFileSize ? ` (${selectedFileSize})` : ''}…</p>
            </>
          ) : (
            <>
              <span style={{ fontSize: 28, display: 'block', marginBottom: 6 }}>🎬</span>
              <p style={{ fontSize: 13, fontWeight: 600, color: A.text, margin: '0 0 4px' }}>
                Drop a video here or click to browse
              </p>
              <p style={{ fontSize: 11, color: A.textMuted, margin: 0 }}>
                .mp4 / .mov · up to 500 MB
              </p>
            </>
          )}
        </div>
      )}

      {error && (
        <p style={{ fontSize: 12, color: A.coral, marginTop: 8 }}>{error}</p>
      )}

      {/* Processing state */}
      {isProcessing && (
        <div style={{
          padding: '16px 14px', borderRadius: 10, border: `1px solid ${A.border}`,
          background: A.surface, textAlign: 'center',
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%', margin: '0 auto 10px',
            border: `3px solid ${A.violetLight}`, borderTopColor: A.violet,
            animation: 'vr-spin 0.9s linear infinite',
          }} />
          <p style={{ fontSize: 13, fontWeight: 600, color: A.text, margin: '0 0 4px' }}>
            {job.status === 'queued' ? 'Queued for processing…' : 'Analyzing your video…'}
          </p>
          <p style={{ fontSize: 11, color: A.textMuted, margin: 0, lineHeight: 1.4 }}>
            Gemini is identifying the best moments. This takes 30–90 seconds.
          </p>
          {job.filename && (
            <p style={{ fontSize: 11, color: A.textSoft, marginTop: 8, animation: 'vr-pulse 2s ease-in-out infinite' }}>
              {job.filename}
            </p>
          )}
        </div>
      )}

      {/* Failed state */}
      {isFailed && (
        <div style={{
          padding: '14px', borderRadius: 10,
          border: `1px solid ${A.coral}40`, background: A.coralLight,
        }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: A.coral, margin: '0 0 6px' }}>
            Processing failed
          </p>
          {job.error && (
            <p style={{ fontSize: 11, color: A.coral, margin: '0 0 10px', lineHeight: 1.4 }}>
              {job.error}
            </p>
          )}
          <button
            onClick={() => { setJob(null); setError(''); sessionStorage.removeItem(storageKey) }}
            style={{
              padding: '6px 14px', borderRadius: 6, border: `1px solid ${A.coral}60`,
              background: 'white', color: A.coral, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      )}

      {/* Success — clip cards */}
      {isDone && job.clips.length > 0 && (
        <div>
          <div style={{
            marginBottom: 12, padding: '8px 12px', borderRadius: 8,
            background: A.emeraldLight, border: `1px solid ${A.emerald}30`,
            fontSize: 12, color: A.emerald,
          }}>
            ✓ {job.clips.length} clip{job.clips.length !== 1 ? 's' : ''} ready to download
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {job.clips.map((clip, i) => {
              const repurposeInfo = REPURPOSE_LABELS[clip.platform]
              const spec = getPlatform(repurposeInfo?.platformKey ?? clip.platform)
              const PlatIcon = spec.icon
              const platLabel = repurposeInfo?.label ?? spec.displayName
              return (
                <div key={i} style={{
                  borderRadius: 10, border: `1px solid ${A.border}`,
                  background: A.surface, overflow: 'hidden',
                }}>
                  {/* Platform header */}
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 12px',
                    background: spec.color + '12',
                    borderBottom: `1px solid ${A.border}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <PlatIcon size={16} color={spec.color} />
                      <span style={{ fontSize: 13, fontWeight: 700, color: A.text }}>{platLabel}</span>
                      <span style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 20,
                        background: A.surfaceAlt, color: A.textSoft, border: `1px solid ${A.borderLight}`,
                      }}>
                        {clip.duration_seconds}s
                      </span>
                      {clip.content_theme && (
                        <span style={{
                          fontSize: 10, padding: '2px 8px', borderRadius: 20,
                          background: A.indigo + '18', color: A.indigo, fontWeight: 600,
                          border: `1px solid ${A.indigo}30`,
                        }}>
                          {clip.content_theme}
                        </span>
                      )}
                    </div>
                    {clip.clip_url && <a
                      href={clip.clip_url}
                      download={clip.filename}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        padding: '5px 12px', borderRadius: 6, border: 'none',
                        background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                        color: 'white', fontSize: 11, fontWeight: 600,
                        textDecoration: 'none', cursor: 'pointer',
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                      }}
                    >
                      ↓ Download
                    </a>}
                  </div>

                  {/* Video preview */}
                  {clip.clip_url && (
                    <div style={{ padding: '8px 12px 0' }}>
                      <video
                        src={clip.clip_url}
                        controls
                        preload="none"
                        aria-label={`${platLabel} clip preview`}
                        style={{
                          width: '100%', borderRadius: 6,
                          background: '#000', maxHeight: 300,
                          objectFit: 'contain',
                        }}
                      />
                    </div>
                  )}

                  {/* Clip details */}
                  <div style={{ padding: '10px 12px' }}>
                    {clip.hook && (
                      <p style={{ fontSize: 12, fontWeight: 600, color: A.text, margin: '0 0 4px', lineHeight: 1.4 }}>
                        Hook: <span style={{ fontWeight: 400, fontStyle: 'italic' }}>"{clip.hook}"</span>
                      </p>
                    )}
                    {clip.suggested_caption && (
                      <p style={{ fontSize: 11, color: A.textSoft, margin: '4px 0 0', lineHeight: 1.5 }}>
                        {clip.suggested_caption}
                      </p>
                    )}
                    {clip.reason && (
                      <p style={{ fontSize: 11, color: A.textSoft, margin: '6px 0 0', lineHeight: 1.5, fontStyle: 'italic' }}>
                        Why this clip: {clip.reason}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          <button
            onClick={() => { setJob(null); setError(''); sessionStorage.removeItem(storageKey) }}
            style={{
              marginTop: 12, padding: '7px 14px', borderRadius: 6,
              border: `1px solid ${A.border}`, background: 'transparent',
              color: A.textSoft, fontSize: 12, cursor: 'pointer',
            }}
          >
            Upload another video
          </button>
        </div>
      )}
    </div>
  )
}
