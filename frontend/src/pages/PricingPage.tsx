import { A } from '../theme'

export default function PricingPage() {
  return (
    <div style={{ maxWidth: 600, margin: '80px auto', padding: '0 24px', textAlign: 'center' }}>
      <h1 style={{ fontSize: 32, fontWeight: 700, color: A.text }}>Pricing</h1>
      <p style={{ color: A.textSoft, marginTop: 12 }}>Coming soon. Contact us to upgrade your account.</p>
      <a href="mailto:dimitri.derose@deepvalueanalysis.io" style={{ color: A.indigo }}>
        dimitri.derose@deepvalueanalysis.io
      </a>
    </div>
  )
}
