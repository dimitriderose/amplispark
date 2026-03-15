import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { A } from '../theme'
import { useAuth } from '../hooks/useAuth'
import { useIsMobile } from '../hooks/useIsMobile'
import { api } from '../api/client'

interface BrandSummary {
  brand_id: string
  business_name?: string
  industry?: string
  analysis_status?: string
  description?: string
}

const PAGE_SIZE = 5

export default function BrandsPage() {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const { uid, isSignedIn, loading } = useAuth()
  const [brands, setBrands] = useState<BrandSummary[]>([])
  const [page, setPage] = useState(0)

  useEffect(() => {
    if (!loading && !isSignedIn) {
      navigate('/')
    }
  }, [loading, isSignedIn, navigate])

  useEffect(() => {
    if (!uid) return
    api.listBrands(uid)
      .then((res) => setBrands((res as unknown as { brands: BrandSummary[] }).brands || []))
      .catch(() => {})
  }, [uid])

  if (loading) return null

  const totalPages = Math.max(1, Math.ceil(brands.length / PAGE_SIZE))
  const pageBrands = brands.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div style={{ minHeight: '100vh', background: A.bg }}>
      <div style={{ maxWidth: 860, margin: '0 auto', padding: isMobile ? '24px 12px' : '48px 24px' }}>

        {/* ── Create Your Brand ── */}
        <section style={{
          padding: 32,
          borderRadius: 16,
          border: `1px solid ${A.border}`,
          background: A.surface,
          textAlign: 'center',
          marginBottom: 48,
        }}>
          <h2 style={{ fontSize: 24, fontWeight: 700, color: A.text, marginBottom: 8 }}>
            Create Your Brand
          </h2>
          <p style={{ fontSize: 14, color: A.textSoft, marginBottom: 24, maxWidth: 420, margin: '0 auto 24px' }}>
            Describe your business, get an AI-powered content strategy, and generate a week of posts in minutes.
          </p>
          <button
            onClick={() => navigate('/onboard')}
            style={{
              padding: '12px 32px',
              borderRadius: 10,
              border: 'none',
              cursor: 'pointer',
              background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
              color: 'white',
              fontSize: 15,
              fontWeight: 600,
              boxShadow: `0 8px 32px ${A.indigo}40`,
            }}
          >
            + New Brand
          </button>
        </section>

        {/* ── Your Brands ── */}
        <section>
          <h3 style={{
            fontSize: 14, fontWeight: 600, color: A.textSoft,
            marginBottom: 16, textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            Your Brands
          </h3>

          {brands.length === 0 ? (
            <div style={{
              padding: 48,
              borderRadius: 14,
              border: `1px dashed ${A.border}`,
              textAlign: 'center',
            }}>
              <p style={{ fontSize: 15, color: A.textMuted, marginBottom: 8 }}>
                No brands yet
              </p>
              <p style={{ fontSize: 13, color: A.textMuted }}>
                Create your first brand to get started with AI-powered content.
              </p>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {pageBrands.map((b) => (
                  <button
                    key={b.brand_id}
                    onClick={() => navigate(`/dashboard/${b.brand_id}`)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: `1px solid ${A.border}`,
                      background: A.surface,
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                      transition: 'border-color 0.15s, box-shadow 0.15s',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = A.indigo + '50'
                      e.currentTarget.style.boxShadow = `0 2px 12px ${A.indigo}15`
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = A.border
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <div style={{
                      width: 40,
                      height: 40,
                      borderRadius: 10,
                      background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'white',
                      fontSize: 17,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}>
                      {(b.business_name || b.description || '?')[0].toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 600, color: A.text }}>
                        {b.business_name || b.description?.slice(0, 40) || 'Untitled Brand'}
                      </div>
                      {b.industry && (
                        <div style={{ fontSize: 12, color: A.textMuted, marginTop: 2 }}>
                          {b.industry}
                        </div>
                      )}
                    </div>
                    <span style={{
                      fontSize: 11,
                      fontWeight: 500,
                      color: b.analysis_status === 'complete' ? A.emerald : A.amber,
                      padding: '3px 10px',
                      borderRadius: 10,
                      background: (b.analysis_status === 'complete' ? A.emerald : A.amber) + '15',
                    }}>
                      {b.analysis_status === 'complete' ? 'Ready' : b.analysis_status || 'Pending'}
                    </span>
                    <span style={{ color: A.textMuted, fontSize: 16 }}>&rarr;</span>
                  </button>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={{
                  display: 'flex', justifyContent: 'center', alignItems: 'center',
                  gap: 16, marginTop: 24,
                }}>
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    style={{
                      padding: '6px 14px', borderRadius: 8,
                      border: `1px solid ${A.border}`, background: 'transparent',
                      cursor: page === 0 ? 'default' : 'pointer',
                      fontSize: 13, fontWeight: 500,
                      color: page === 0 ? A.textMuted : A.text,
                      opacity: page === 0 ? 0.5 : 1,
                    }}
                  >
                    Previous
                  </button>
                  <span style={{ fontSize: 13, color: A.textSoft }}>
                    Page {page + 1} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    style={{
                      padding: '6px 14px', borderRadius: 8,
                      border: `1px solid ${A.border}`, background: 'transparent',
                      cursor: page >= totalPages - 1 ? 'default' : 'pointer',
                      fontSize: 13, fontWeight: 500,
                      color: page >= totalPages - 1 ? A.textMuted : A.text,
                      opacity: page >= totalPages - 1 ? 0.5 : 1,
                    }}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  )
}
