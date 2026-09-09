import { useEffect, useState } from 'react'
import './App.css'
import { ApplyPage } from './pages/Apply'
import { EmailPage } from './pages/Email'
import { JobFeedPage } from './pages/JobFeed'
import { ResumeEditor } from './pages/ResumeEditor'
import { ResumeLibrary } from './pages/ResumeLibrary'
import { ReviewPage } from './pages/Review'
import { SettingsPage } from './pages/Settings'

const phases = [
  {
    name: 'Resume Management',
    desc: 'Upload, parse to schema, edit, set active per run',
    href: '#/resumes',
    pill: 'Live',
  },
  { name: 'Source Ingestion', desc: 'Scan Greenhouse & Lever for postings', href: '#/jobs', pill: 'Live' },
  {
    name: 'AI Matching',
    desc: 'Hybrid keyword + semantic scoring with reasons',
    href: '#/jobs',
    pill: 'Live',
  },
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
  {
    name: 'Email Ingestion & Reply',
    desc: 'Pull related emails via Microsoft Graph',
    href: '#/email',
    pill: 'Live',
  },
  { name: 'Learning Loop', desc: 'Adjust matching weights from user decisions', pill: 'Planned' },
  {
    name: 'Settings',
    desc: 'Threshold, email connection, source toggles',
    href: '#/settings',
    pill: 'Live',
  },
]

type Route =
  | { name: 'home' }
  | { name: 'review' }
  | { name: 'apply'; requestId: string | null }
  | { name: 'settings' }
  | { name: 'library' }
  | { name: 'edit'; id: string }
  | { name: 'jobs' }
  | { name: 'email' }

function parseRoute(hash: string): Route {
  const raw = (hash.replace(/^#/, '') || '/').split('?')[0]
  const path = raw.startsWith('/') ? raw : `/${raw}`
  if (path === '/review') return { name: 'review' }
  if (path === '/settings') return { name: 'settings' }
  if (path === '/resumes') return { name: 'library' }
  if (path === '/jobs') return { name: 'jobs' }
  if (path === '/email') return { name: 'email' }
  const edit = path.match(/^\/resumes\/([^/]+)\/edit$/)
  if (edit) return { name: 'edit', id: decodeURIComponent(edit[1]) }
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
        <span className="badge">Phase 7</span>
        <h1>AJAS</h1>
        <p className="tagline">AI Job Application System</p>
      </header>

      <main>
        <p className="intro">
          Resume Management, the job feed with match scores, Review, Auto-Apply, Email, and Settings are live.
          Upload a resume, scan Greenhouse and Lever, review scores, apply, and reply to recruiter mail in-app.
          The learning loop follows <code>.codespring/CURSOR_RUNBOOK.md</code>.
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
  if (route.name === 'settings') return <SettingsPage />
  if (route.name === 'library') return <ResumeLibrary />
  if (route.name === 'jobs') return <JobFeedPage />
  if (route.name === 'email') return <EmailPage />
  if (route.name === 'edit') {
    return (
      <ResumeEditor
        resumeId={route.id}
        onBack={() => {
          window.location.hash = '#/resumes'
        }}
        onSaved={() => undefined}
      />
    )
  }
  return <Home />
}

export default App
