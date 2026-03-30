import { useState } from 'react'
import { A } from '../theme'
import { api } from '../api/client'
import { getPlatform } from '../platformRegistry'

// Module-level keyframe — avoids duplicate injection on remount
const SPIN_STYLE = `@keyframes sc-spin { to { transform: rotate(360deg); } }`

interface VoiceAnalysis {
  voice_characteristics: string[]
  common_phrases: string[]
  emoji_usage: string
  average_post_length: string
  successful_patterns: string[]
  tone_adjectives: string[]
}

interface PlatformConfig {
  name: string
  tokenLabel: string
  tokenPlaceholder: string
  helpText: string
  helpUrl: string
}

const PLATFORMS: Record<string, PlatformConfig> = {
  linkedin: {
    name: 'LinkedIn',
    tokenLabel: 'LinkedIn OAuth 2.0 Access Token',
    tokenPlaceholder: 'AQX... (from LinkedIn Developer Portal)',
    helpText: 'Get a token from LinkedIn Developer Portal → OAuth 2.0 tools → Generate token (scopes: r_liteprofile, r_member_social)',
    helpUrl: 'https://www.linkedin.com/developers/tools/oauth',
  },
  instagram: {
    name: 'Instagram',
    tokenLabel: 'Instagram User Access Token',
    tokenPlaceholder: 'IGQ... (from Meta Graph API Explorer)',
    helpText: 'Get a token from Meta for Developers → Graph API Explorer → select your Instagram app',
    helpUrl: 'https://developers.facebook.com/tools/explorer/',
  },
  x: {
    name: 'X (Twitter)',
    tokenLabel: 'X OAuth 2.0 User Access Token',
    tokenPlaceholder: 'AAAA... (from X Developer Portal)',
    helpText: 'Get a token from X Developer Portal → Your App → Keys and Tokens → OAuth 2.0 User Access Token',
    helpUrl: 'https://developer.x.com/en/portal/dashboard',
  },
}

interface PlatformCardProps {
  platformKey: string
  config: PlatformConfig
  brandId: string
  isConnected: boolean
  existingAnalysis?: VoiceAnalysis
  onConnected: (platform: string, analysis: VoiceAnalysis) => void
  onLoadDemo?: () => void
}

function PlatformCard({ platformKey, config, brandId, isConnected, existingAnalysis, onConnected, onLoadDemo }: PlatformCardProps) {
  const spec = getPlatform(platformKey)
  const PlatIcon = spec.icon
  const [expanded, setExpanded] = useState(false)
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [analysis, setAnalysis] = useState<VoiceAnalysis | null>(existingAnalysis ?? null)

  const handleConnect = async () => {
    if (!token.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await api.connectSocial(brandId, platformKey, token.trim()) as unknown as {
        platform: string
        voice_analysis: VoiceAnalysis
      }
      setAnalysis(res.voice_analysis)
      onConnected(platformKey, res.voice_analysis)
      setToken('')
      setExpanded(false)
    } catch (err: any) {
      setError(err.message || 'Connection failed')
    } finally {
      setLoading(false)
    }
  }

  const connected = isConnected || !!analysis

  return (
    <div style={{
      borderRadius: 10,
      border: `1px solid ${connected ? spec.color + '40' : A.border}`,
      background: connected ? spec.color + '08' : A.surface,
      overflow: 'hidden',
      transition: 'border-color 0.2s, background 0.2s',
    }}>
      {/* Header row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 14px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <PlatIcon size={18} color={spec.color} />
          <span style={{ fontSize: 13, fontWeight: 600, color: A.text }}>{config.name}</span>
          {connected && (
            <span style={{
              fontSize: 11, fontWeight: 500,
              padding: '2px 8px', borderRadius: 20,
              background: A.emeraldLight,
              color: A.emerald,
            }}>
              ✓ Connected
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!connected && onLoadDemo && !expanded && (
            <button
              type="button"
              onClick={onLoadDemo}
              style={{
                padding: '2px 4px', border: 'none', background: 'transparent',
                color: A.indigo, fontSize: 11, cursor: 'pointer', textDecoration: 'underline',
              }}
            >
              try demo
            </button>
          )}
          <button
            onClick={() => setExpanded(v => !v)}
            style={{
              padding: '5px 12px', borderRadius: 6, border: `1px solid ${A.border}`,
              background: 'transparent', color: A.textSoft, fontSize: 12, cursor: 'pointer',
            }}
          >
            {connected ? 'Reconnect' : expanded ? 'Cancel' : 'Connect'}
          </button>
        </div>
      </div>

      {/* Voice analysis summary — shown when connected */}
      {connected && analysis && !expanded && (
        <div style={{ padding: '0 14px 12px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {analysis.tone_adjectives.slice(0, 4).map((adj, i) => (
              <span key={i} style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 20,
                background: A.surfaceAlt, color: A.textSoft, border: `1px solid ${A.borderLight}`,
              }}>
                {adj}
              </span>
            ))}
            {analysis.emoji_usage !== 'none' && (
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 20,
                background: A.surfaceAlt, color: A.textSoft, border: `1px solid ${A.borderLight}`,
              }}>
                emoji: {analysis.emoji_usage}
              </span>
            )}
          </div>
          {analysis.voice_characteristics.length > 0 && (
            <p style={{ fontSize: 11, color: A.textMuted, margin: '6px 0 0', lineHeight: 1.4 }}>
              {analysis.voice_characteristics.slice(0, 2).join(' · ')}
            </p>
          )}
        </div>
      )}

      {/* Token input form */}
      {expanded && (
        <div style={{ padding: '0 14px 14px', borderTop: `1px solid ${A.border}` }}>
          <div style={{ paddingTop: 12 }}>
            <label
              htmlFor={`token-${platformKey}`}
              style={{ fontSize: 12, fontWeight: 500, color: A.textSoft, display: 'block', marginBottom: 6 }}
            >
              {config.tokenLabel}
            </label>
            <input
              id={`token-${platformKey}`}
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleConnect()}
              placeholder={config.tokenPlaceholder}
              autoFocus
              style={{
                width: '100%', padding: '8px 12px', borderRadius: 6,
                border: `1px solid ${A.border}`, fontSize: 13,
                color: A.text, background: A.surface, outline: 'none',
              }}
            />
            <p style={{ fontSize: 11, color: A.textMuted, marginTop: 6, lineHeight: 1.5 }}>
              {config.helpText}{' '}
              <a
                href={config.helpUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: A.indigo }}
              >
                Open portal ↗
              </a>
            </p>

            {error && (
              <p style={{ fontSize: 12, color: A.coral, marginTop: 6 }}>{error}</p>
            )}

            <button
              onClick={handleConnect}
              disabled={loading || !token.trim()}
              style={{
                marginTop: 10, padding: '8px 16px', borderRadius: 7, border: 'none',
                cursor: loading || !token.trim() ? 'not-allowed' : 'pointer',
                background: loading || !token.trim()
                  ? A.surfaceAlt
                  : `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                color: loading || !token.trim() ? A.textMuted : 'white',
                fontSize: 13, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 8,
              }}
            >
              {loading ? (
                <>
                  <span style={{
                    display: 'inline-block', width: 12, height: 12, borderRadius: '50%',
                    border: `2px solid ${A.textMuted}`, borderTopColor: 'transparent',
                    animation: 'sc-spin 0.8s linear infinite',
                  }} />
                  Analyzing posts...
                </>
              ) : `Analyze ${config.name} voice`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

interface Props {
  brandId: string
  connectedPlatforms?: string[]
  /** Per-platform voice analyses keyed by platform name (preferred) */
  existingVoiceAnalyses?: Record<string, VoiceAnalysis>
  /** Fallback: single latest analysis (older brands) */
  existingVoiceAnalysis?: VoiceAnalysis
  existingVoicePlatform?: string
}

// DK-4: Per-platform demo analyses so every supported platform has realistic sample data
const DEMO_VOICE_ANALYSES: Record<string, VoiceAnalysis> = {
  instagram: {
    voice_characteristics: ['Conversational and warm', 'Uses storytelling to connect with audience'],
    common_phrases: ['Behind the scenes', 'Made with love', 'Fresh from the oven'],
    emoji_usage: 'moderate',
    average_post_length: 'medium (100–150 words)',
    successful_patterns: ['Personal anecdotes', 'Behind-the-scenes content', 'Product launch teasers'],
    tone_adjectives: ['authentic', 'warm', 'community-driven', 'artisanal'],
  },
  linkedin: {
    voice_characteristics: ['Direct and practical', 'Uses specific examples from real situations', 'Avoids buzzwords and generic advice'],
    common_phrases: ['Here\'s what I\'ve learned', 'The conversation most leaders avoid', 'After 15 years of'],
    emoji_usage: 'none',
    average_post_length: 'long (250–400 words)',
    successful_patterns: ['Opens with a counterintuitive observation', 'Shares a specific failure and what it taught', 'Ends with a single actionable takeaway'],
    tone_adjectives: ['authoritative', 'candid', 'specific', 'no-nonsense'],
  },
  x: {
    voice_characteristics: ['Punchy and opinionated', 'Uses hot-take framing to spark discussion', 'Thread hooks that demand a click'],
    common_phrases: ['Hot take:', 'Unpopular opinion:', 'Nobody talks about this but'],
    emoji_usage: 'minimal',
    average_post_length: 'short (under 280 chars)',
    successful_patterns: ['Single sharp observation', 'Contrarian framing of conventional wisdom', 'Question that challenges assumptions'],
    tone_adjectives: ['sharp', 'opinionated', 'direct', 'provocative'],
  },
}

export default function SocialConnect({
  brandId,
  connectedPlatforms = [],
  existingVoiceAnalyses,
  existingVoiceAnalysis,
  existingVoicePlatform,
}: Props) {
  const [connected, setConnected] = useState<string[]>(connectedPlatforms)
  const [sessionAnalyses, setSessionAnalyses] = useState<Record<string, VoiceAnalysis>>({})

  const handleConnected = (platform: string, analysis: VoiceAnalysis) => {
    setConnected(prev => prev.includes(platform) ? prev : [...prev, platform])
    setSessionAnalyses(prev => ({ ...prev, [platform]: analysis }))
  }

  // Resolve per-platform analysis: session state wins, then per-platform dict, then single fallback
  const getAnalysisForPlatform = (key: string): VoiceAnalysis | undefined => {
    if (sessionAnalyses[key]) return sessionAnalyses[key]
    if (existingVoiceAnalyses?.[key]) return existingVoiceAnalyses[key]
    if (existingVoiceAnalysis && existingVoicePlatform === key) return existingVoiceAnalysis
    return undefined
  }

  const hasAnyActive =
    connected.length > 0 ||
    Object.keys(sessionAnalyses).length > 0 ||
    (existingVoiceAnalyses != null && Object.keys(existingVoiceAnalyses).length > 0) ||
    (existingVoiceAnalysis != null && existingVoicePlatform != null)

  return (
    <div>
      <style>{SPIN_STYLE}</style>

      <div style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: A.text, margin: '0 0 4px' }}>
          Social Voice Analysis
        </h3>
        <p style={{ fontSize: 12, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
          Connect a social account so Amplispark can match your existing writing style when generating captions.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* DK-4: Each platform card gets its own "demo" link so any platform can be previewed */}
        {Object.entries(PLATFORMS).map(([key, config]) => (
          <PlatformCard
            key={key}
            platformKey={key}
            config={config}
            brandId={brandId}
            isConnected={connected.includes(key)}
            existingAnalysis={getAnalysisForPlatform(key)}
            onConnected={handleConnected}
            onLoadDemo={DEMO_VOICE_ANALYSES[key] ? () => handleConnected(key, DEMO_VOICE_ANALYSES[key]) : undefined}
          />
        ))}
      </div>

      {hasAnyActive && (
        <div style={{
          marginTop: 12, padding: '10px 12px', borderRadius: 8,
          background: A.indigoLight, border: `1px solid ${A.indigo}20`,
          fontSize: 12, color: A.indigo, lineHeight: 1.5,
        }}>
          ✓ Voice analysis active — captions will match your connected account style.
        </div>
      )}
    </div>
  )
}
