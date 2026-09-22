import { lazy, Suspense, useEffect, useState } from 'react'
import './App.css'
import { AppNav } from './components/AppNav'
import { CookieBanner } from './components/CookieBanner'
import { captureAadTokenFromHash } from './api/live'
import { jobsApi, matchingApi, reviewApi, settingsApi } from './api'
import { filtersForTab } from './lib/review'
import { onboardingSteps, type OnboardingStep } from './lib/onboarding'
import { bannerNeeded } from './lib/cookieConsent'
import { applyTheme, readThemePref, resolveTheme } from './lib/theme'
import { tourSteps } from './lib/sprint12'

const ReviewPage = lazy(() => import('./pages/Review').then((mod) => ({ default: mod.ReviewPage })))
const ApplyPage = lazy(() => import('./pages/Apply').then((mod) => ({ default: mod.ApplyPage })))
const SettingsPage = lazy(() => import('./pages/Settings').then((mod) => ({ default: mod.SettingsPage })))
const ResumeLibrary = lazy(() => import('./pages/ResumeLibrary').then((mod) => ({ default: mod.ResumeLibrary })))
const ResumeEditor = lazy(() => import('./pages/ResumeEditor').then((mod) => ({ default: mod.ResumeEditor })))
const JobFeedPage = lazy(() => import('./pages/JobFeed').then((mod) => ({ default: mod.JobFeedPage })))
const EmailPage = lazy(() => import('./pages/Email').then((mod) => ({ default: mod.EmailPage })))
const LearningPage = lazy(() => import('./pages/Learning').then((mod) => ({ default: mod.LearningPage })))
const MatchesPage = lazy(() => import('./pages/Matches').then((mod) => ({ default: mod.MatchesPage })))
const OpsPage = lazy(() => import('./pages/Ops').then((mod) => ({ default: mod.OpsPage })))
const AdminPage = lazy(() => import('./pages/Admin').then((mod) => ({ default: mod.AdminPage })))
const HelpPage = lazy(() => import('./pages/Help').then((mod) => ({ default: mod.HelpPage })))
const ChangelogPage = lazy(() => import('./pages/Changelog').then((mod) => ({ default: mod.ChangelogPage })))
const LegalPage = lazy(() => import('./pages/Legal').then((mod) => ({ default: mod.LegalPage })))
const SharePage = lazy(() => import('./pages/Share').then((mod) => ({ default: mod.SharePage })))

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
    href: '#/matches',
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
  {
    name: 'Learning Loop',
    desc: 'Adjust matching weights from user decisions',
    href: '#/learning',
    pill: 'Live',
  },
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
  | { name: 'matches' }
  | { name: 'email' }
  | { name: 'learning' }
  | { name: 'ops' }
  | { name: 'admin' }
  | { name: 'help' }
  | { name: 'changelog' }
  | { name: 'legal' }
  | { name: 'share'; token: string }

function parseRoute(hash: string): Route {
  const raw = (hash.replace(/^#/, '') || '/').split('?')[0]
  const path = raw.startsWith('/') ? raw : `/${raw}`
  if (path === '/review') return { name: 'review' }
  if (path === '/settings') return { name: 'settings' }
  if (path === '/resumes') return { name: 'library' }
  if (path === '/jobs') return { name: 'jobs' }
  if (path === '/matches') return { name: 'matches' }
  if (path === '/email') return { name: 'email' }
  if (path === '/learning') return { name: 'learning' }
  if (path === '/ops') return { name: 'ops' }
  if (path === '/admin') return { name: 'admin' }
  if (path === '/help') return { name: 'help' }
  if (path === '/changelog') return { name: 'changelog' }
  if (path === '/legal') return { name: 'legal' }
  const share = path.match(/^\/share\/([^/]+)$/)
  if (share) return { name: 'share', token: decodeURIComponent(share[1]) }
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
  const [steps, setSteps] = useState<OnboardingStep[] | null>(null)
  const [cookies, setCookies] = useState(() => bannerNeeded())

  useEffect(() => {
    const systemDark = globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
    applyTheme(resolveTheme(readThemePref(), systemDark))
  }, [])

  useEffect(() => {
    void matchingApi.warmup().catch(() => undefined)
    void (async () => {
      try {
        const [settings, sources, history] = await Promise.all([
          settingsApi.get(),
          jobsApi.sourceStatus().catch(() => []),
          reviewApi.list('history', filtersForTab('history')).catch(() => ({ items: [], total: 0 })),
        ])
        const emailOk =
          settings.emailConnection.status === 'connected' || settings.emailConnection.status === 'pending'
        const sourceOk = sources.some((item) => (item.boards || []).length > 0) ||
          settings.sources.greenhouseEnabled ||
          settings.sources.leverEnabled
        setSteps(
          onboardingSteps({
            emailConnected: emailOk,
            sourceEnabled: Boolean(sourceOk),
            thresholdSet: settings.matchThreshold > 0,
            reviewed: history.total > 0 || history.items.length > 0,
          }),
        )
      } catch {
        setSteps(
          onboardingSteps({
            emailConnected: false,
            sourceEnabled: false,
            thresholdSet: false,
            reviewed: false,
          }),
        )
      }
    })()
  }, [])

  return (
    <div className="page">
      <AppNav />
      <header className="header">
        <span className="badge">Live</span>
        <h1>AJAS</h1>
        <p className="tagline">AI Job Application System</p>
      </header>

      <main>
        <p className="intro">
          Resume Management, the job feed with match scores, Review, Auto-Apply, Email, Learning, and Settings
          are live. Upload a resume, scan Greenhouse and Lever, review scores (matches at or above your
          threshold land in Review), apply, reply to recruiter mail, and let approve/reject decisions tune
          ranking.
        </p>

        {cookies && <CookieBanner onSave={() => setCookies(false)} />}

        {steps && (
          <section className="onboarding" aria-labelledby="onboarding-heading">
            <h2 id="onboarding-heading">First-run checklist</h2>
            <ol>
              {steps.map((step) => (
                <li key={step.id} className={step.done ? 'is-done' : undefined}>
                  <a href={step.href}>
                    <span aria-hidden="true">{step.done ? '✓' : '○'}</span> {step.label}
                  </a>
                </li>
              ))}
            </ol>
          </section>
        )}

        <section className="onboarding" aria-labelledby="tour-heading">
          <h2 id="tour-heading">Tour</h2>
          <ol>
            {tourSteps().map((step) => (
              <li key={step.id}>
                <a href={step.href}>{step.title}</a>
              </li>
            ))}
          </ol>
        </section>

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

      <footer className="footer">
        Azure Functions · Cosmos DB · Blob &amp; Queue Storage · Azure OpenAI ·{' '}
        <a href="#/legal">Legal</a> · <a href="#/changelog">Changelog</a>
      </footer>
    </div>
  )
}

function RouteFallback() {
  return (
    <div className="page">
      <AppNav />
      <p className="skeleton">Loading…</p>
    </div>
  )
}

function App() {
  const route = useHashRoute()
  const [cookies, setCookies] = useState(() => bannerNeeded())
  useEffect(() => {
    captureAadTokenFromHash()
  }, [route])
  useEffect(() => {
    const systemDark = globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
    applyTheme(resolveTheme(readThemePref(), systemDark))
  }, [])
  let page
  if (route.name === 'review') page = <ReviewPage />
  else if (route.name === 'apply') page = <ApplyPage requestId={route.requestId} />
  else if (route.name === 'settings') page = <SettingsPage />
  else if (route.name === 'library') page = <ResumeLibrary />
  else if (route.name === 'jobs') page = <JobFeedPage />
  else if (route.name === 'matches') page = <MatchesPage />
  else if (route.name === 'email') page = <EmailPage />
  else if (route.name === 'learning') page = <LearningPage />
  else if (route.name === 'ops') page = <OpsPage />
  else if (route.name === 'admin') page = <AdminPage />
  else if (route.name === 'help') page = <HelpPage />
  else if (route.name === 'changelog') page = <ChangelogPage />
  else if (route.name === 'legal') page = <LegalPage />
  else if (route.name === 'share') page = <SharePage token={route.token} />
  else if (route.name === 'edit') {
    page = (
      <ResumeEditor
        resumeId={route.id}
        onBack={() => {
          window.location.hash = '#/resumes'
        }}
        onSaved={() => undefined}
      />
    )
  } else page = <Home />
  return (
    <Suspense fallback={<RouteFallback />}>
      {page}
      {cookies && route.name !== 'home' ? <CookieBanner onSave={() => setCookies(false)} /> : null}
    </Suspense>
  )
}

export default App
