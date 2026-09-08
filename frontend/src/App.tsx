import { useEffect, useState } from 'react'
import './App.css'
import { ReviewPage } from './pages/Review'

const phases = [
  { name: 'Resume Management', desc: 'Upload, parse to schema, edit, set active per run', pill: 'Planned' },
  { name: 'Source Ingestion', desc: 'Scan Greenhouse & Lever for postings', pill: 'Planned' },
  { name: 'AI Matching', desc: 'Hybrid keyword + semantic scoring with reasons', pill: 'Planned' },
  {
    name: 'Review & Decision',
    desc: 'Approve / reject with comments and summary',
    href: '#/review',
    pill: 'Live',
  },
  { name: 'Auto-Apply', desc: 'Auto-fill and submit approved applications', pill: 'Planned' },
  { name: 'Email Ingestion & Reply', desc: 'Pull related emails via Microsoft Graph', pill: 'Planned' },
  { name: 'Learning Loop', desc: 'Adjust matching weights from user decisions', pill: 'Planned' },
  { name: 'Settings', desc: 'Threshold, email connection, source toggles', pill: 'Planned' },
]

type Route = { name: 'home' } | { name: 'review' }

function parseRoute(hash: string): Route {
  const raw = (hash.replace(/^#/, '') || '/').split('?')[0]
  const path = raw.startsWith('/') ? raw : `/${raw}`
  if (path === '/review') return { name: 'review' }
  return { name: 'home' }
}

function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

function Home() {
  return (
    <div className="page">
      <header className="header">
        <span className="badge">Phase 1</span>
        <h1>AJAS</h1>
        <p className="tagline">AI Job Application System</p>
      </header>

      <main>
        <p className="intro">
          Review &amp; Decision is live. Open the queue to approve or reject AI matches with
          optional comments. Other features follow <code>.codespring/CURSOR_RUNBOOK.md</code>.
        </p>

        <ul className="phases">
          {phases.map((phase) => {
            const inner = (
              <>
                <div className="phase-name">{phase.name}</div>
                <div className="phase-desc">{phase.desc}</div>
                <span className={`pill ${phase.pill === 'Live' ? 'pill-live' : ''}`}>{phase.pill}</span>
              </>
            )
            return (
              <li key={phase.name}>
                {phase.href ? (
                  <a className="phase-card phase-card-link" href={phase.href}>
                    {inner}
                  </a>
                ) : (
                  <div className="phase-card">{inner}</div>
                )}
              </li>
            )
          })}
        </ul>
      </main>

      <footer className="footer">Azure Functions · Cosmos DB · Blob &amp; Queue Storage · Azure OpenAI</footer>
    </div>
  )
}

function App() {
  const route = useHashRoute()
  if (route.name === 'review') return <ReviewPage />
  return <Home />
}

export default App
