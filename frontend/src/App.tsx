import { useEffect, useState } from 'react'
import './App.css'
import { ApplyPage } from './pages/Apply'
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
  {
    name: 'Auto-Apply',
    desc: 'Auto-fill and submit approved applications',
    href: '#/apply',
    pill: 'Live',
  },
  { name: 'Email Ingestion & Reply', desc: 'Pull related emails via Microsoft Graph', pill: 'Planned' },
  { name: 'Learning Loop', desc: 'Adjust matching weights from user decisions', pill: 'Planned' },
  { name: 'Settings', desc: 'Threshold, email connection, source toggles', pill: 'Planned' },
]

type Route = { name: 'home' } | { name: 'review' } | { name: 'apply'; requestId: string | null }

function parseRoute(hash: string): Route {
  const raw = (hash.replace(/^#/, '') || '/').split('?')[0]
  const path = raw.startsWith('/') ? raw : `/${raw}`
  if (path === '/review') return { name: 'review' }
  if (path === '/apply' || path.startsWith('/apply/')) {
    const rest = path.slice('/apply'.length).replace(/^\//, '')
    return { name: 'apply', requestId: rest || null }
  }
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
        <span className="badge">Phase 2</span>
        <h1>AJAS</h1>
        <p className="tagline">AI Job Application System</p>
      </header>

      <main>
        <p className="intro">
          Review &amp; Decision and Auto-Apply are live. Approve matches, then submit Greenhouse
          or Lever applications — or generate a manual package when programmatic submit is blocked.
          Remaining features follow <code>.codespring/CURSOR_RUNBOOK.md</code>.
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
  if (route.name === 'apply') return <ApplyPage requestId={route.requestId} />
  return <Home />
}

export default App
