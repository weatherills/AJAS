import { AppNav } from '../components/AppNav'
import { labelledBy } from '../lib/sprint12'

export function LegalPage() {
  return (
    <div className="page library-page" {...labelledBy('legal-h')}>
      <AppNav />
      <header className="library-header">
        <div>
          <h1 id="legal-h">Legal</h1>
          <p className="tagline">Terms and privacy, version 2026-09-13.</p>
        </div>
      </header>
      <section id="terms" className="editor-section">
        <h2>Terms of use</h2>
        <p>AJAS is a job-seeker tool. Optional adapters stay off until you enable them.</p>
      </section>
      <section id="privacy" className="editor-section">
        <h2>Privacy</h2>
        <p>Download or forget your data from Settings. Consent choices live in the cookie banner.</p>
      </section>
    </div>
  )
}
