import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  isChunkError: boolean
}

export default class ChunkErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, isChunkError: false }
  }

  static getDerivedStateFromError(error: unknown): State {
    const name = error instanceof Error ? error.name : ''
    const msg  = error instanceof Error ? error.message : String(error)

    const isChunkError =
      name === 'ChunkLoadError' ||
      msg.includes('Failed to fetch dynamically imported module') ||
      msg.includes('Importing a module script failed') ||
      msg.includes('error loading dynamically imported module')

    return { hasError: true, isChunkError }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ChunkErrorBoundary] Page chunk failed to load:', {
      name: error.name,
      message: error.message,
      componentStack: info.componentStack,
    })
  }

  private handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '60vh',
          gap: 12,
          textAlign: 'center',
          padding: '0 24px',
        }}>
          <p style={{ color: '#555', fontSize: 15, margin: 0 }}>
            {this.state.isChunkError
              ? 'A new version of Amplispark was deployed. Reload to continue.'
              : 'Something went wrong loading this page.'}
          </p>
          <button
            onClick={this.handleReload}
            style={{
              padding: '8px 20px',
              borderRadius: 8,
              border: '1px solid #ddd',
              background: '#fff',
              color: '#333',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
