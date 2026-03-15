import { useState, useEffect, useRef } from 'react'
import { A } from '../theme'
import { api } from '../api/client'

interface NotionIntegration {
  access_token?: string
  workspace_name?: string
  database_id?: string
  database_name?: string
  connected_at?: string
}

interface Props {
  brandId: string
  notion?: NotionIntegration
  onUpdate: () => void
}

export default function IntegrationConnect({ brandId, notion, onUpdate }: Props) {
  const isConnected = !!notion?.access_token
  const hasDatabase = !!notion?.database_id

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [databases, setDatabases] = useState<{ id: string; title: string }[]>([])
  const [loadingDbs, setLoadingDbs] = useState(false)
  const [dbTimeout, setDbTimeout] = useState(false)
  const dbTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-fetch databases when connected but no database selected
  useEffect(() => {
    if (isConnected && !hasDatabase && databases.length === 0) {
      fetchDatabases()
    }
  }, [isConnected, hasDatabase])

  const handleConnect = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.getNotionAuthUrl(brandId)
      window.location.href = res.auth_url
    } catch (err: any) {
      setError(err.message || 'Failed to get auth URL')
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    setLoading(true)
    setError('')
    try {
      await api.disconnectNotion(brandId)
      setDatabases([])
      onUpdate()
    } catch (err: any) {
      setError(err.message || 'Disconnect failed')
    } finally {
      setLoading(false)
    }
  }

  const fetchDatabases = async () => {
    setLoadingDbs(true)
    setError('')
    setDbTimeout(false)
    if (dbTimeoutRef.current) clearTimeout(dbTimeoutRef.current)
    dbTimeoutRef.current = setTimeout(() => {
      setDbTimeout(true)
      setLoadingDbs(false)
    }, 10000)
    try {
      const res = await api.getNotionDatabases(brandId)
      if (dbTimeoutRef.current) clearTimeout(dbTimeoutRef.current)
      setDbTimeout(false)
      setDatabases(res.databases)
    } catch (err: any) {
      if (dbTimeoutRef.current) clearTimeout(dbTimeoutRef.current)
      setError(err.message || 'Failed to load databases')
    } finally {
      setLoadingDbs(false)
    }
  }

  useEffect(() => {
    return () => { if (dbTimeoutRef.current) clearTimeout(dbTimeoutRef.current) }
  }, [])

  const handleSelectDatabase = async (dbId: string, dbName: string) => {
    setLoading(true)
    setError('')
    try {
      await api.selectNotionDatabase(brandId, dbId, dbName)
      onUpdate()
    } catch (err: any) {
      setError(err.message || 'Failed to select database')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: A.text, margin: '0 0 4px' }}>
          Publish & Export
        </h3>
        <p style={{ fontSize: 12, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
          Connect integrations to publish content directly from Amplifi.
        </p>
      </div>

      {/* Notion Card */}
      <div style={{
        borderRadius: 10,
        border: `1px solid ${isConnected ? '#000000' + '40' : A.border}`,
        background: isConnected ? '#00000008' : A.surface,
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 18 }}>📓</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: A.text }}>Notion</span>
            {isConnected && (
              <span style={{
                fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 20,
                background: A.emeraldLight, color: A.emerald,
              }}>
                ✓ Connected
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {isConnected ? (
              <button
                onClick={handleDisconnect}
                disabled={loading}
                style={{
                  padding: '5px 12px', borderRadius: 6, border: `1px solid ${A.border}`,
                  background: 'transparent', color: A.textSoft, fontSize: 12, cursor: 'pointer',
                }}
              >
                Disconnect
              </button>
            ) : (
              <button
                onClick={handleConnect}
                disabled={loading}
                style={{
                  padding: '5px 12px', borderRadius: 6, border: 'none',
                  background: loading ? A.surfaceAlt : '#000000',
                  color: loading ? A.textMuted : 'white',
                  fontSize: 12, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Connecting...' : 'Connect with Notion'}
              </button>
            )}
          </div>
        </div>

        {/* Connected state — workspace + database info */}
        {isConnected && (
          <div style={{ padding: '0 14px 12px' }}>
            {notion?.workspace_name && (
              <p style={{ fontSize: 12, color: A.textSoft, margin: '0 0 8px' }}>
                Workspace: <strong style={{ color: A.text }}>{notion.workspace_name}</strong>
              </p>
            )}

            {hasDatabase ? (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 8,
                  background: A.indigoLight, color: A.indigo, fontWeight: 500,
                }}>
                  📋 {notion?.database_name || 'Selected database'}
                </span>
                <button
                  onClick={fetchDatabases}
                  style={{
                    fontSize: 11, color: A.textMuted, background: 'transparent',
                    border: 'none', cursor: 'pointer', textDecoration: 'underline',
                  }}
                >
                  change
                </button>
              </div>
            ) : (
              <div>
                <p style={{ fontSize: 12, color: A.amber, margin: '0 0 8px' }}>
                  Select a database to export your content calendar to:
                </p>
                {dbTimeout ? (
                  <div>
                    <p style={{ fontSize: 12, color: A.coral, margin: '0 0 6px' }}>
                      Couldn't load databases — the request timed out.
                    </p>
                    <button
                      onClick={fetchDatabases}
                      style={{
                        padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.coral}60`,
                        background: 'transparent', color: A.coral, fontSize: 11, cursor: 'pointer',
                      }}
                    >
                      ↻ Retry
                    </button>
                  </div>
                ) : loadingDbs ? (
                  <p style={{ fontSize: 12, color: A.textMuted }}>Loading databases...</p>
                ) : databases.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {databases.map(db => (
                      <button
                        key={db.id}
                        onClick={() => handleSelectDatabase(db.id, db.title)}
                        disabled={loading}
                        style={{
                          padding: '8px 12px', borderRadius: 6,
                          border: `1px solid ${A.border}`, background: A.surface,
                          color: A.text, fontSize: 12, cursor: 'pointer',
                          textAlign: 'left',
                        }}
                      >
                        📋 {db.title || 'Untitled'}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: 12, color: A.textMuted, margin: '0 0 6px' }}>
                      No databases found. Create a database in Notion first, then click refresh.
                    </p>
                    <button
                      onClick={fetchDatabases}
                      disabled={loadingDbs}
                      style={{
                        padding: '4px 10px', borderRadius: 6, border: `1px solid ${A.border}`,
                        background: 'transparent', color: A.textSoft, fontSize: 11, cursor: 'pointer',
                      }}
                    >
                      ↻ Refresh
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <div style={{ padding: '0 14px 12px' }}>
            <p style={{ fontSize: 12, color: A.coral, margin: 0 }}>{error}</p>
          </div>
        )}
      </div>
    </div>
  )
}
