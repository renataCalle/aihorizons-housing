import { Link } from 'react-router'
import { BrandMark } from '../components/BrandMark'

const SAMPLE_LOT_A = '0000X00000000000'

/** Placeholder until M2: brand, headline and a link that proves the API round trip. */
export function LandingPage() {
  return (
    <main className="page page-center">
      <header className="topbar glass">
        <BrandMark />
      </header>
      <section className="hero">
        <p className="label">Pittsburgh site screening</p>
        <h1 className="hero-title">What can you build here?</h1>
        <p className="hero-sub">Search is coming in M2. For now, open the sample report.</p>
        <Link className="button-primary" to={`/parcel/${SAMPLE_LOT_A}`}>
          Open Sample lot A
        </Link>
      </section>
    </main>
  )
}
