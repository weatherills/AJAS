import { AppNav } from '../components/AppNav'
import { labelledBy } from '../lib/sprint12'

export function SharePage({ token }: { token: string }) {
  return (
    <div className="page library-page" {...labelledBy('share-h')}>
      <AppNav />
      <header className="library-header">
        <div>
          <h1 id="share-h">Shared match</h1>
          <p className="tagline">Limited recruiter view. Token {token.slice(0, 8)}…</p>
        </div>
      </header>
      <p className="muted">Scores and highlights only. Resume files stay private.</p>
    </div>
  )
}
