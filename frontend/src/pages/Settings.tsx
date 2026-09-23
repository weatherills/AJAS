import { useCallback, useEffect, useRef, useState } from 'react'
import { getUserId, jobsApi, learningApi, resumeApi, setUserId, settingsApi, USE_MOCK } from '../api'
import { json, request, fetchAuthConfig, type AuthConfig } from '../api/live'
import { liveLinkedInApi } from '../api/linkedinLive'
import type { LinkedInSessionAccount } from '../api/linkedinLive'
import { loadLinkedInAccountId, saveLinkedInAccountId } from '../lib/linkedin'
import type { SettingsAuditItem, SettingsDoc } from '../api/settingsTypes'
import type { JobSourceName, SourceStatus } from '../api/jobsTypes'
import { AppNav } from '../components/AppNav'
import { Modal } from '../components/Modal'
import { ToastStack } from '../components/Toast'
import {
  asStrictness,
  STRICTNESS_HELP,
  STRICTNESS_LABEL,
} from '../lib/learning'
import {
  apiToPercent,
  clampPercent,
  emailUiState,
  isOAuthNotConfiguredError,
  isSourceNotConfiguredError,
  OAUTH_MESSAGE_TYPE,
  oauthIsConfigured,
  percentToApi,
  previewCopy,
  SLIDER_MAX,
  SLIDER_MIN,
  SLIDER_STEP,
  sourceIsConfigured,
  sourceUnconfiguredCopy,
} from '../lib/settings'
import { loadApplyPrefs, saveApplyPrefs, type ApplyPrefs } from '../lib/applyPrefs'
import { buildExportBundle } from '../lib/privacy'
import {
  exportAuditCsv,
  forgetPreview,
  loadSiteOverrides,
  loadSuppressed,
  saveSiteOverride,
  syncSuppressed,
  validateOverride,
} from '../lib/sprint15Kanban'
import { emailProviderHealth } from '../lib/emailHealth'
import { formatAllowlist, parseAllowlist, recordAllowlistAudit } from '../lib/allowlist'
import { currentLocale, setLocale, t, type Locale } from '../lib/i18n'
import { flagRows, mergeFlags } from '../lib/flags'
import { evaluateLimit, remainingInWindow, windowLabel, type SiteLimit } from '../lib/automationLimits'
import {
  addBoardToast,
  boardAddPayload,
  boardErrorCopy,
  boardInputHint,
  sourceIsConfiguredStatus,
  sourceTitle,
} from '../lib/jobs'
import { LearningPanel } from './Learning'
import { loadRedactionFields, saveRedactionFields, type RedactionField } from '../lib/sprint13'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }
type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

function oauthRedirectUri() {
  return `${window.location.origin}/oauth-callback.html`
}

function formatWhen(stamp: string | null) {
  if (!stamp) return null
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return stamp
  return date.toLocaleString()
}

function SuppressionList() {
  const [blocked, setBlocked] = useState(() => loadSuppressed())
  const [draft, setDraft] = useState('')
  return (
    <div>
      <label>
        Address
        <input value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Suppressed email address" />
      </label>
      <button
        type="button"
        className="secondary"
        onClick={() => {
          if (!draft.trim()) return
          setBlocked(syncSuppressed([draft.trim()], []))
          setDraft('')
        }}
      >
        Suppress
      </button>
      <ul>
        {blocked.map((addr) => (
          <li key={addr}>
            {addr}{' '}
            <button type="button" className="link-btn" onClick={() => setBlocked(syncSuppressed([], [addr]))}>
              Restore
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ApplyPrefsFields() {
  const [prefs, setPrefs] = useState<ApplyPrefs>(() => loadApplyPrefs())
  const [resumes, setResumes] = useState<{ id: string; fileName: string }[]>([])
  const [overrides, setOverrides] = useState(() => loadSiteOverrides())
  const [site, setSite] = useState('greenhouse')
  const [nameField, setNameField] = useState('')
  const [emailField, setEmailField] = useState('')
  const [resumeField, setResumeField] = useState('')
  useEffect(() => {
    void resumeApi
      .list()
      .then((items) => setResumes(items.map((item) => ({ id: item.id, fileName: item.fileName }))))
      .catch(() => setResumes([]))
  }, [])
  return (
    <div className="apply-prefs">
      <h3>Apply preferences</h3>
      <p className="muted">Default cover-letter mode and location used when you open Apply from the job feed.</p>
      <label>
        Cover letter
        <select
          value={prefs.defaultCoverMode}
          onChange={(event) => {
            const next = { ...prefs, defaultCoverMode: event.target.value as ApplyPrefs['defaultCoverMode'] }
            setPrefs(next)
            saveApplyPrefs(next)
          }}
          aria-label="Default cover letter mode"
        >
          <option value="none">None</option>
          <option value="generate">Generate</option>
          <option value="upload">Upload / paste</option>
        </select>
      </label>
      <label>
        Cover letter tone
        <select
          value={prefs.coverTone}
          onChange={(event) => {
            const next = { ...prefs, coverTone: event.target.value as ApplyPrefs['coverTone'] }
            setPrefs(next)
            saveApplyPrefs(next)
          }}
          aria-label="Cover letter tone"
        >
          <option value="concise">Concise</option>
          <option value="enthusiastic">Enthusiastic</option>
          <option value="formal">Formal</option>
        </select>
      </label>
      <label>
        Profile location
        <input
          value={prefs.location}
          onChange={(event) => {
            const next = { ...prefs, location: event.target.value }
            setPrefs(next)
            saveApplyPrefs(next)
          }}
          placeholder="Remote, Austin…"
          aria-label="Profile location for matching boosts"
        />
      </label>
      <label>
        Resume / profile version
        <select
          value={prefs.defaultResumeId}
          onChange={(event) => {
            const next = { ...prefs, defaultResumeId: event.target.value }
            setPrefs(next)
            saveApplyPrefs(next)
          }}
          aria-label="Default resume for Auto-Apply"
        >
          <option value="">Active resume</option>
          {resumes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.fileName}
            </option>
          ))}
        </select>
      </label>
      <h3>Per-site form overrides</h3>
      <p className="muted">Map name, email, and resume fields for Greenhouse or Lever Auto-Apply. Changes are audited in this browser.</p>
      <label>
        Site
        <select value={site} onChange={(event) => setSite(event.target.value)} aria-label="Override site">
          <option value="greenhouse">Greenhouse</option>
          <option value="lever">Lever</option>
        </select>
      </label>
      <label>
        Name field
        <input value={nameField} onChange={(event) => setNameField(event.target.value)} aria-label="Name field override" />
      </label>
      <label>
        Email field
        <input value={emailField} onChange={(event) => setEmailField(event.target.value)} aria-label="Email field override" />
      </label>
      <label>
        Resume field
        <input value={resumeField} onChange={(event) => setResumeField(event.target.value)} aria-label="Resume field override" />
      </label>
      <button
        type="button"
        className="secondary"
        onClick={() => {
          const fields = { name: nameField, email: emailField, resume: resumeField }
          const check = validateOverride(fields)
          if (!check.valid) return
          setOverrides(saveSiteOverride(site, fields))
        }}
      >
        Save override
      </button>
      {overrides.length > 0 && (
        <ul>
          {overrides.map((item) => (
            <li key={item.site}>
              {item.site}: {Object.keys(item.fields).join(', ')}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function SettingsPage() {
  const [userId, setUser] = useState(getUserId())
  const [locale, setLocaleState] = useState<Locale>(() => currentLocale())
  const [flagOverrides, setFlagOverrides] = useState<Record<string, boolean>>({})
  const [siteLimits, setSiteLimits] = useState<SiteLimit[]>([
    { site: 'greenhouse', cap: 20, consent: false, used: 0, windowMinutes: 1440 },
    { site: 'lever', cap: 20, consent: false, used: 0, windowMinutes: 1440 },
  ])
  const [redactFields, setRedactFields] = useState<RedactionField[]>(() => loadRedactionFields())
  const [allowlistText, setAllowlistText] = useState('boards.greenhouse.io, jobs.lever.co, graph.microsoft.com')
  const [allowlistAudit, setAllowlistAudit] = useState(() => [recordAllowlistAudit('admin', 'boards.greenhouse.io, jobs.lever.co, graph.microsoft.com')])
  const [doc, setDoc] = useState<SettingsDoc | null>(null)
  const [percent, setPercent] = useState(70)
  const [savedPercent, setSavedPercent] = useState(70)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [thresholdStatus, setThresholdStatus] = useState<SaveStatus>('idle')
  const [thresholdError, setThresholdError] = useState<string | null>(null)
  const [ghStatus, setGhStatus] = useState<SaveStatus>('idle')
  const [leverStatus, setLeverStatus] = useState<SaveStatus>('idle')
  const [sourceError, setSourceError] = useState<string | null>(null)
  const [sourceRetry, setSourceRetry] = useState<{
    key: 'greenhouseEnabled' | 'leverEnabled'
    value: boolean
  } | null>(null)
  const [sourceStatus, setSourceStatus] = useState<SourceStatus[]>([])
  const [ghBoard, setGhBoard] = useState('')
  const [leverBoard, setLeverBoard] = useState('')
  const [ghAddStatus, setGhAddStatus] = useState<SaveStatus>('idle')
  const [leverAddStatus, setLeverAddStatus] = useState<SaveStatus>('idle')
  const [removingKey, setRemovingKey] = useState<string | null>(null)
  const [retryingKey, setRetryingKey] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<{ name: JobSourceName; tenantKey: string } | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [popupBlocked, setPopupBlocked] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [oauthBlocked, setOauthBlocked] = useState(false)
  const [pendingAuthUrl, setPendingAuthUrl] = useState<string | null>(null)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [tuningMode, setTuningMode] = useState<'auto' | 'manual'>('auto')
  const [strictness, setStrictness] = useState<0 | 1 | 2>(1)
  const [learningError, setLearningError] = useState<string | null>(null)
  const [learningSample, setLearningSample] = useState(0)
  const [learningStatus, setLearningStatus] = useState<SaveStatus>('idle')
  const [learningTick, setLearningTick] = useState(0)
  const [autoApplyEnabled, setAutoApplyEnabled] = useState(true)
  const [autoApplyStatus, setAutoApplyStatus] = useState<SaveStatus>('idle')
  const [auditItems, setAuditItems] = useState<SettingsAuditItem[]>([])
  const [devices, setDevices] = useState<{ id: string; label: string; createdAt: string; lastSeenAt: string }[]>([])
  const [sessionBusy, setSessionBusy] = useState(false)
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null)
  const [linkedinAccountId, setLinkedinAccountId] = useState(() => loadLinkedInAccountId())
  const [linkedinToken, setLinkedinToken] = useState('')
  const [linkedinAccounts, setLinkedinAccounts] = useState<LinkedInSessionAccount[]>([])
  const [linkedinLive, setLinkedinLive] = useState(false)
  const [linkedinBusy, setLinkedinBusy] = useState(false)
  const [linkedinError, setLinkedinError] = useState<string | null>(null)
  const toastId = useRef(1)
  const saveGen = useRef(0)
  const oauthState = useRef<string | null>(null)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const applyDoc = useCallback((next: SettingsDoc) => {
    setDoc(next)
    const value = apiToPercent(next.matchThreshold)
    setPercent(value)
    setSavedPercent(value)
    if (next.autoApplyEnabled != null) setAutoApplyEnabled(next.autoApplyEnabled)
    if (next.oauthConfigured === false) setOauthBlocked(true)
    else if (next.oauthConfigured === true) setOauthBlocked(false)
  }, [])

  const load = useCallback(async () => {
    try {
      setSourceStatus(await jobsApi.sourceStatus())
    } catch {
      /* source status is additive; settings toggles still render */
    }
    try {
      applyDoc(await settingsApi.get())
      try {
        setAuditItems((await settingsApi.listAudit()).items)
      } catch {
        setAuditItems([])
      }
      try {
        const page = await json<{ items: { id: string; label: string; createdAt: string; lastSeenAt: string }[] }>(
          await request('/api/v1/auth/devices'),
        )
        setDevices(page.items)
      } catch {
        setDevices([])
      }
      try {
        setAuthConfig(await fetchAuthConfig())
      } catch {
        setAuthConfig(null)
      }
      try {
        const linkedin = await liveLinkedInApi.status()
        setLinkedinLive(Boolean(linkedin.linkedinLive))
        setLinkedinAccounts(linkedin.linkedinAccounts || [])
        const listed = await liveLinkedInApi.listSessions()
        setLinkedinAccounts(listed.accounts || linkedin.linkedinAccounts || [])
      } catch {
        setLinkedinAccounts([])
      }
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Could not load settings')
    }
  }, [applyDoc])

  useEffect(() => {
    void load()
  }, [load, userId])

  useEffect(() => {
    void (async () => {
      try {
        const params = await learningApi.params()
        setTuningMode(params.tuningMode)
        setStrictness(asStrictness(params.strictness))
        setLearningSample(params.sample_size)
        setLearningError(null)
      } catch (err) {
        setLearningError(err instanceof Error ? err.message : 'Could not load matching preferences')
      }
    })()
  }, [userId])

  const failedPercent = useRef<number | null>(null)

  const saveThreshold = useCallback(
    async (value: number) => {
      const gen = ++saveGen.current
      setThresholdStatus('saving')
      setThresholdError(null)
      try {
        const next = await settingsApi.patch({ matchThreshold: percentToApi(value) })
        if (gen !== saveGen.current) return
        failedPercent.current = null
        applyDoc(next)
        setThresholdStatus('saved')
      } catch {
        if (gen !== saveGen.current) return
        failedPercent.current = value
        setThresholdStatus('error')
        setThresholdError('Couldn’t save threshold. Try again.')
      }
    },
    [applyDoc],
  )

  useEffect(() => {
    if (!doc) return
    if (percent === savedPercent) return
    if (failedPercent.current === percent) return
    const handle = window.setTimeout(() => {
      void saveThreshold(percent)
    }, 600)
    return () => window.clearTimeout(handle)
  }, [percent, savedPercent, doc, saveThreshold])

  async function saveLearning(body: { tuningMode?: 'auto' | 'manual'; strictness?: number }) {
    setLearningStatus('saving')
    setLearningError(null)
    try {
      const patched = await learningApi.patchParams(body)
      setTuningMode(patched.tuningMode)
      setStrictness(asStrictness(patched.strictness))
      setLearningSample(patched.sample_size)
      setLearningStatus('saved')
      setLearningTick((tick) => tick + 1)
      const learnedPercent = Math.round(patched.score_threshold * 100)
      if (Number.isFinite(learnedPercent)) {
        try {
          const next = await settingsApi.patch({ matchThreshold: percentToApi(learnedPercent) })
          applyDoc(next)
        } catch {
          /* learning prefs saved even if settings threshold sync fails */
        }
      }
      toast('Preferences updated. Takes effect on new suggestions.')
    } catch {
      setLearningStatus('error')
      setLearningError('Couldn’t save matching preferences. Try again.')
    }
  }

  async function saveSource(key: 'greenhouseEnabled' | 'leverEnabled', value: boolean) {
    if (!doc) return
    const name = key === 'greenhouseEnabled' ? 'greenhouse' : 'lever'
    if (value && !sourceConfigured(name)) {
      setSourceError(sourceUnconfiguredCopy(name))
      return
    }
    const previous = doc.sources[key]
    const setStatus = key === 'greenhouseEnabled' ? setGhStatus : setLeverStatus
    setDoc({ ...doc, sources: { ...doc.sources, [key]: value } })
    setStatus('saving')
    setSourceError(null)
    setSourceRetry(null)
    try {
      const next = await settingsApi.patch({ sources: { [key]: value } })
      applyDoc(next)
      setStatus('saved')
    } catch (err) {
      setDoc({ ...doc, sources: { ...doc.sources, [key]: previous } })
      setStatus('error')
      if (isSourceNotConfiguredError(err)) {
        setSourceError(err instanceof Error ? err.message : sourceUnconfiguredCopy(key === 'greenhouseEnabled' ? 'greenhouse' : 'lever'))
        setSourceRetry(null)
        return
      }
      setSourceError('Couldn’t save source toggle. Try again.')
      setSourceRetry({ key, value })
    }
  }

  async function addBoard(name: 'greenhouse' | 'lever') {
    if (!doc) return
    const value = (name === 'greenhouse' ? ghBoard : leverBoard).trim()
    const enabledKey = name === 'greenhouse' ? 'greenhouseEnabled' : 'leverEnabled'
    const setAddStatus = name === 'greenhouse' ? setGhAddStatus : setLeverAddStatus
    const setToggleStatus = name === 'greenhouse' ? setGhStatus : setLeverStatus
    if (!value) {
      setSourceError(sourceUnconfiguredCopy(name))
      return
    }
    const alreadyOn = Boolean(doc.sources[enabledKey]) && sourceConfigured(name)
    setAddStatus('saving')
    setSourceError(null)
    setSourceRetry(null)
    try {
      const created = await jobsApi.addTenant(name, boardAddPayload(value))
      const next = await settingsApi.patch({ sources: { [enabledKey]: true } })
      applyDoc(next)
      let rows = created.sources?.length ? created.sources : await jobsApi.sourceStatus()
      const added = addBoardToast(name, created)
      if (added.tone !== 'error') {
        try {
          rows = alreadyOn
            ? await jobsApi.refresh(name)
            : await jobsApi.refreshTenant(name, created.tenantKey)
        } catch {
          /* tenant is saved; refresh can retry from Job Feed */
        }
      }
      setSourceStatus(rows)
      if (name === 'greenhouse') setGhBoard('')
      else setLeverBoard('')
      setAddStatus('saved')
      setToggleStatus('saved')
      toast(added.text, added.tone)
    } catch (err) {
      setAddStatus('error')
      setSourceError(err instanceof Error ? err.message : `Couldn’t add the ${sourceTitle(name)} board.`)
    }
  }

  async function removeBoard(name: JobSourceName, tenantKey: string) {
    const setAddStatus = name === 'greenhouse' ? setGhAddStatus : setLeverAddStatus
    const setToggleStatus = name === 'greenhouse' ? setGhStatus : setLeverStatus
    setConfirmRemove(null)
    setRemovingKey(`${name}:${tenantKey}`)
    setSourceError(null)
    setSourceRetry(null)
    try {
      const removed = await jobsApi.removeTenant(name, tenantKey)
      try {
        applyDoc(await settingsApi.get())
      } catch {
        /* source status still updates the Not configured badge */
      }
      setSourceStatus(removed.sources?.length ? removed.sources : await jobsApi.sourceStatus())
      setAddStatus('idle')
      setToggleStatus('saved')
      toast(`${sourceTitle(name)} board “${removed.tenantKey}” removed`)
    } catch (err) {
      setSourceError(err instanceof Error ? err.message : `Couldn’t remove the ${sourceTitle(name)} board.`)
    } finally {
      setRemovingKey(null)
    }
  }

  async function retryBoard(name: JobSourceName, tenantKey: string) {
    setRetryingKey(`${name}:${tenantKey}`)
    setSourceError(null)
    setSourceRetry(null)
    try {
      const rows = await jobsApi.refreshTenant(name, tenantKey)
      setSourceStatus(rows)
      const row = rows.find((item) => item.source === name)
      const boards = row?.boards || []
      const board = boards.find((item) => item.tenantKey === tenantKey)
      const err = row && board ? boardErrorCopy(board, row, boards.length) : null
      if (err) toast(err, 'error')
      else toast(`${sourceTitle(name)} board “${tenantKey}” refreshed`)
    } catch (err) {
      setSourceError(err instanceof Error ? err.message : `Couldn’t retry the ${sourceTitle(name)} board.`)
    } finally {
      setRetryingKey(null)
    }
  }

  function listenForOAuth(expectedState: string) {
    return new Promise<{ code: string; state: string }>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        cleanup()
        reject(new Error('Microsoft sign-in timed out'))
      }, 5 * 60 * 1000)
      const onMessage = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return
        const data = event.data as {
          type?: string
          code?: string | null
          state?: string | null
          error?: string | null
        }
        if (data?.type !== OAUTH_MESSAGE_TYPE) return
        cleanup()
        if (data.error) {
          reject(
            new Error(data.error === 'access_denied' ? 'Microsoft consent was cancelled' : 'Microsoft sign-in failed'),
          )
          return
        }
        if (!data.code || data.state !== expectedState) {
          reject(new Error('Microsoft sign-in returned an invalid state'))
          return
        }
        resolve({ code: data.code, state: data.state })
      }
      const cleanup = () => {
        window.clearTimeout(timer)
        window.removeEventListener('message', onMessage)
      }
      window.addEventListener('message', onMessage)
    })
  }

  async function startConnect(authUrl?: string | null) {
    setEmailError(null)
    setPopupBlocked(false)
    const configured = oauthIsConfigured(doc?.oauthConfigured) && !oauthBlocked
    if (!configured && !authUrl) {
      setOauthBlocked(true)
      setEmailError(null)
      return
    }
    try {
      let url = authUrl
      let state = oauthState.current
      const redirectUri = oauthRedirectUri()
      if (!url) {
        const started = await settingsApi.connectEmail(redirectUri)
        if (started.noOp) {
          await load()
          return
        }
        url = started.authUrl
        state = started.state
        oauthState.current = state
      }
      if (!url || !state) throw new Error('Microsoft sign-in did not return a URL')
      setConnecting(true)
      setPendingAuthUrl(url)
      const popup = window.open(url, 'ajas-ms-oauth', 'popup=yes,width=520,height=720')
      if (!popup) {
        setPopupBlocked(true)
        setConnecting(false)
        setEmailError('The Microsoft window was blocked. Allow popups, then retry.')
        return
      }
      const result = await listenForOAuth(state)
      const next = await settingsApi.emailCallback({ ...result, redirectUri })
      applyDoc(next)
      setConnecting(false)
      setPendingAuthUrl(null)
      oauthState.current = null
      toast('Microsoft 365 connected')
    } catch (err) {
      setConnecting(false)
      if (isOAuthNotConfiguredError(err)) {
        setOauthBlocked(true)
        setEmailError(null)
        await load()
        return
      }
      setEmailError(err instanceof Error ? err.message : 'Could not connect Microsoft 365')
      await load()
    }
  }

  async function disconnect() {
    setConfirmDisconnect(false)
    try {
      applyDoc(await settingsApi.disconnectEmail())
      toast('Disconnected')
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : 'Could not disconnect')
    }
  }

  const email = doc?.emailConnection
  const configured = oauthIsConfigured(doc?.oauthConfigured) && !oauthBlocked
  const ui = emailUiState(email?.status ?? 'disconnected', email?.errorCode, connecting, configured)

  function sourceConfigured(name: JobSourceName): boolean {
    const key = name === 'greenhouse' ? 'greenhouseConfigured' : 'leverConfigured'
    const fromSettings = sourceIsConfigured(doc?.sources[key])
    const row = sourceStatus.find((item) => item.source === name)
    if (row && !sourceIsConfiguredStatus(row)) return false
    return fromSettings
  }

  return (
    <div className="page library-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>{t('settings')}</h1>
          <p className="tagline">Match threshold, learning, Microsoft 365 email, and job sources.</p>
        </div>
        {!doc && !loadError && (
          <section className="editor-section" aria-busy="true" aria-label="Loading settings">
            <div className="skeleton settings-skel" />
            <div className="skeleton settings-skel" />
            <div className="skeleton settings-skel" />
          </section>
        )}
        <label className="user-field">
          Signed in as
          <input
            value={userId}
            onChange={(event) => {
              setUser(event.target.value)
              setUserId(event.target.value)
            }}
            aria-label="User id"
          />
        </label>
      </header>

      {USE_MOCK && <p className="banner">Demo data (mock API). Settings stay in this browser session.</p>}
      {loadError && <p className="inline-error">{loadError}</p>}

      <section className="editor-section" aria-labelledby="threshold-heading">
        <h2 id="threshold-heading">Matching threshold</h2>
        <p className="muted">Jobs below this score are not saved. Default is 70%.</p>
        <div className="slider-row">
          <span className="muted">More matches</span>
          <input
            id="match-threshold"
            type="range"
            min={SLIDER_MIN}
            max={SLIDER_MAX}
            step={SLIDER_STEP}
            value={percent}
            aria-valuemin={SLIDER_MIN}
            aria-valuemax={SLIDER_MAX}
            aria-valuenow={percent}
            aria-valuetext={`${percent} percent. ${previewCopy(percent)}`}
            aria-label="Match threshold"
            onChange={(event) => {
              const next = clampPercent(Number(event.target.value))
              setPercent(next)
            }}
            onKeyDown={(event) => {
              if (event.key === 'PageUp') {
                event.preventDefault()
                setPercent((value) => clampPercent(value + 10))
              }
              if (event.key === 'PageDown') {
                event.preventDefault()
                setPercent((value) => clampPercent(value - 10))
              }
            }}
          />
          <span className="muted">Fewer matches</span>
        </div>
        <p className="threshold-value">
          <strong>{percent}%</strong> — {previewCopy(percent)}
        </p>
        <p className="save-status" aria-live="polite">
          {thresholdStatus === 'saving' && 'Saving…'}
          {thresholdStatus === 'saved' && 'Saved'}
          {thresholdStatus === 'error' && thresholdError}
        </p>
        {thresholdStatus === 'error' && (
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={() => {
                failedPercent.current = null
                void saveThreshold(percent)
              }}
            >
              Retry
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                failedPercent.current = null
                setPercent(savedPercent)
                setThresholdStatus('idle')
                setThresholdError(null)
              }}
            >
              Revert
            </button>
          </div>
        )}
      </section>

      <section className="editor-section" aria-labelledby="auto-apply-heading">
        <h2 id="auto-apply-heading">Auto-Apply</h2>
        <p className="muted">Turn off to hide Apply in Review until you are ready to submit applications.</p>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={autoApplyEnabled}
            onChange={(event) => {
              const next = event.target.checked
              setAutoApplyEnabled(next)
              setAutoApplyStatus('saving')
              void settingsApi
                .patch({ autoApplyEnabled: next })
                .then((doc) => {
                  applyDoc(doc)
                  setAutoApplyStatus('saved')
                  toast(next ? 'Auto-Apply enabled' : 'Auto-Apply disabled')
                  return settingsApi.listAudit().catch(() => ({ items: [] as SettingsAuditItem[] }))
                })
                .then((page) => setAuditItems(page.items))
                .catch((err) => {
                  setAutoApplyEnabled(!next)
                  setAutoApplyStatus('error')
                  toast(err instanceof Error ? err.message : 'Could not save Auto-Apply', 'error')
                })
            }}
          />
          Auto-Apply is {autoApplyEnabled ? 'on' : 'off'}
        </label>
        <p className="save-status" aria-live="polite">
          {autoApplyStatus === 'saving' && 'Saving…'}
          {autoApplyStatus === 'saved' && 'Saved'}
        </p>
        <ApplyPrefsFields />
      </section>

      <section className="editor-section" aria-labelledby="privacy-heading">
        <h2 id="privacy-heading">Privacy</h2>
        <p className="muted">Download a GDPR bundle of jobs, emails, and matches stored for this user.</p>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            const bundle = buildExportBundle(userId)
            const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `ajas-gdpr-${userId}.json`
            link.click()
            URL.revokeObjectURL(url)
          }}
        >
          Download my data
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            const plan = forgetPreview(userId)
            window.alert(`Dry-run right-to-be-forgotten for ${plan.userId} (${plan.deleted} stored rows). Nothing was deleted.`)
          }}
        >
          Forget my account
        </button>
        <fieldset className="redact-fields">
          <legend>Field-level log redaction</legend>
          <p className="muted">Strip these fields from operator logs and exports for this browser.</p>
          {(['email', 'phone', 'resume'] as RedactionField[]).map((field) => (
            <label key={field}>
              <input
                type="checkbox"
                checked={redactFields.includes(field)}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...new Set([...redactFields, field])]
                    : redactFields.filter((item) => item !== field)
                  setRedactFields(saveRedactionFields(next))
                }}
              />
              Redact {field}
            </label>
          ))}
        </fieldset>
        <h3>Email suppression list</h3>
        <p className="muted">Addresses on this list skip outbound mail until restored.</p>
        <SuppressionList />
      </section>

      <section className="editor-section" aria-labelledby="allowlist-heading">
        <h2 id="allowlist-heading">Outbound domain allowlist</h2>
        <p className="muted">Admin policy for hosts Auto-Apply and adapters may call. Comma-separated hostnames.</p>
        <label>
          Allowed hosts
          <textarea
            value={allowlistText}
            onChange={(event) => {
              const next = event.target.value
              setAllowlistText(next)
              setAllowlistAudit((prev) => [recordAllowlistAudit(userId, next), ...prev].slice(0, 8))
            }}
            aria-label="Outbound domain allowlist"
            rows={3}
          />
        </label>
        <p className="muted">Normalized: {formatAllowlist(parseAllowlist(allowlistText))}</p>
        <ul className="audit-list" aria-label="Allowlist audit">
          {allowlistAudit.slice(0, 3).map((row, index) => (
            <li key={`${row.actor}-${index}`}>
              {row.actor} {row.action} ({row.hosts.join(', ') || 'empty'})
            </li>
          ))}
        </ul>
      </section>

      <section className="editor-section" aria-labelledby="flags-heading">
        <h2 id="flags-heading">Feature flags</h2>
        <p className="muted">Adapter, matching algorithm, and automation flags. Optional boards stay off unless an operator enables the matching env var. Toggles here are a preview of FLAG_* defaults.</p>
        <ul>
          {flagRows(mergeFlags(flagOverrides)).map((row) => (
            <li key={row.id}>
              <label>
                <input
                  type="checkbox"
                  checked={row.on}
                  disabled={row.id === 'respect_robots' || row.id === 'greenhouse' || row.id === 'lever'}
                  onChange={(event) => setFlagOverrides((prev) => ({ ...prev, [row.id]: event.target.checked }))}
                />{' '}
                {row.id}
              </label>
            </li>
          ))}
        </ul>
        <p className="muted">Greenhouse/Lever production adapters stay on. Robots stays on.</p>
      </section>

      <section className="editor-section" aria-labelledby="automation-limits-heading">
        <h2 id="automation-limits-heading">Automation limits</h2>
        <p className="muted">Per-site rate windows and explicit consent before Auto-Apply may submit.</p>
        {siteLimits.map((row, index) => {
          const gate = evaluateLimit(row)
          return (
            <div key={row.site} className="source-board-row">
              <label>
                <input
                  type="checkbox"
                  checked={row.consent}
                  onChange={(event) => {
                    const next = [...siteLimits]
                    next[index] = { ...row, consent: event.target.checked }
                    setSiteLimits(next)
                  }}
                />{' '}
                Consent {row.site}
              </label>
              <label>
                Daily cap
                <input
                  type="number"
                  min={1}
                  value={row.cap}
                  aria-label={`${row.site} daily cap`}
                  onChange={(event) => {
                    const next = [...siteLimits]
                    next[index] = { ...row, cap: Number(event.target.value) || 0 }
                    setSiteLimits(next)
                  }}
                />
              </label>
              <label>
                Window (minutes)
                <input
                  type="number"
                  min={15}
                  value={row.windowMinutes ?? 1440}
                  aria-label={`${row.site} rate window minutes`}
                  onChange={(event) => {
                    const next = [...siteLimits]
                    next[index] = { ...row, windowMinutes: Number(event.target.value) || 1440 }
                    setSiteLimits(next)
                  }}
                />
              </label>
              <p className="muted">
                {gate.allowed ? `Ready · ${remainingInWindow(row)} left (${windowLabel(row)})` : `Blocked: ${gate.reason}`}
              </p>
            </div>
          )
        })}
      </section>

      <section className="editor-section" aria-labelledby="allowlist-heading-lang">
        <label>
          {t('language')}
          <select
            value={locale}
            onChange={(event) => setLocaleState(setLocale(event.target.value))}
            aria-label={t('language')}
          >
            <option value="en">English</option>
          </select>
        </label>
      </section>

      <section className="editor-section" aria-labelledby="learning-prefs-heading">
        <h2 id="learning-prefs-heading">Matching preferences</h2>
        <p className="muted">Auto-tune ranking from Review decisions, or set match strictness yourself.</p>
        {learningError && learningStatus === 'idle' && <p className="inline-error">{learningError}</p>}
        <div className="segmented" role="group" aria-label="Tuning mode">
          {(['auto', 'manual'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              className={tuningMode === mode ? 'is-selected' : ''}
              onClick={() => {
                if (tuningMode === mode) return
                void saveLearning({ tuningMode: mode, strictness: mode === 'manual' ? strictness : undefined })
              }}
            >
              {mode === 'auto' ? 'Auto' : 'Manual'}
            </button>
          ))}
        </div>
        {tuningMode === 'auto' && learningSample < 5 && (
          <p className="banner">We’ll adapt after your first few choices.</p>
        )}
        {tuningMode === 'auto' && learningSample >= 5 && (
          <p className="muted">Adjusted from your last {Math.min(learningSample, 30)} decisions.</p>
        )}
        <div className="slider-row">
          <span className="muted">Conservative</span>
          <input
            id="match-strictness"
            type="range"
            min={0}
            max={2}
            step={1}
            value={strictness}
            disabled={tuningMode === 'auto'}
            aria-valuemin={0}
            aria-valuemax={2}
            aria-valuenow={strictness}
            aria-valuetext={STRICTNESS_LABEL[strictness]}
            aria-label="Match strictness"
            onChange={(event) => {
              const next = asStrictness(Number(event.target.value))
              if (next === strictness) return
              setStrictness(next)
              void saveLearning({ tuningMode: 'manual', strictness: next })
            }}
          />
          <span className="muted">Adventurous</span>
        </div>
        <p className="threshold-value">
          <strong>{STRICTNESS_LABEL[strictness]}</strong> — {STRICTNESS_HELP[strictness]}
        </p>
        <p className="save-status" aria-live="polite">
          {learningStatus === 'saving' && 'Saving…'}
          {learningStatus === 'saved' && 'Saved'}
          {learningStatus === 'error' && learningError}
        </p>
        {learningStatus === 'error' && (
          <button
            type="button"
            className="primary"
            onClick={() => void saveLearning({ tuningMode, strictness: tuningMode === 'manual' ? strictness : undefined })}
          >
            Retry
          </button>
        )}
        <LearningPanel compact key={learningTick} />
      </section>

      <section className="editor-section" aria-labelledby="email-heading">
        <h2 id="email-heading">Email connection</h2>
        <p className="muted">
          AJAS requests the least privilege needed to ingest recruiter mail and send replies from this app:{' '}
          <code>Mail.Read</code>, <code>Mail.Send</code>, and <code>offline_access</code>. We do not ask for mailbox
          admin or directory scopes. Microsoft will show this consent list before you connect.
        </p>
        {(() => {
          const health = emailProviderHealth({
            connected: ui === 'connected',
            graphConnected: ui === 'connected',
            address: email?.accountId || null,
            lastSyncedAt: email?.lastVerifiedAt || null,
            unreadCount: 0,
            demo: ui !== 'connected',
            oauthConfigured: configured,
            lastSyncError: ui === 'error' || ui === 'action_required' ? emailError : null,
            provider: 'microsoft365',
          })
          return (
            <p className={health.ok ? 'muted' : 'inline-error'} role="status">
              Provider {health.provider}: {health.label}
              {health.lastError ? ` · ${health.lastError}` : ''}
              {health.reconnect ? ' · Reconnect required' : ''}
            </p>
          )
        })()}
        {ui === 'unconfigured' && (
          <div className="oauth-unconfigured" role="status">
            <p>
              <span className="status-badge status-needs-review">OAuth not configured</span>
            </p>
            <p>
              Microsoft 365 sign-in is not available on this server. Graph app credentials are
              missing, so Connect cannot open a real Microsoft login.
            </p>
            <p className="muted">
              This is not a mailbox problem. Email still shows a local demo inbox until an operator
              sets MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET.
            </p>
          </div>
        )}
        {doc && ui === 'disconnected' && (
          <button type="button" className="primary" onClick={() => void startConnect()}>
            Connect Microsoft 365
          </button>
        )}
        {ui === 'connecting' && (
          <p className="banner" aria-live="polite">
            Continue in Microsoft window…
          </p>
        )}
        {ui === 'connected' && (
          <div className="email-connected">
            <p>
              <span className="status-badge status-ready">Connected</span> {email?.accountId}
            </p>
            {email?.lastVerifiedAt && <p className="muted">Last verified {formatWhen(email.lastVerifiedAt)}</p>}
            <div className="actions">
              {configured ? (
                <button type="button" onClick={() => void startConnect()}>
                  Reconnect
                </button>
              ) : (
                <p className="muted">Reconnect is unavailable until Graph OAuth is configured on this server.</p>
              )}
              <button type="button" className="danger" onClick={() => setConfirmDisconnect(true)}>
                Disconnect
              </button>
            </div>
          </div>
        )}
        {ui === 'action_required' && (
          <div>
            <p>
              <span className="status-badge status-needs-review">Action required</span> Sign in again to keep email
              ingestion running.
            </p>
            <button type="button" className="primary" onClick={() => void startConnect()}>
              Reconnect
            </button>
          </div>
        )}
        {ui === 'error' && (
          <p className="inline-error" role="alert">
            {emailError || 'Microsoft connection failed.'}
          </p>
        )}
        {ui === 'error' && (
          <button type="button" className="primary" onClick={() => void startConnect()}>
            Retry
          </button>
        )}
        {popupBlocked && (
          <p className="warn-text">
            Allow popups for this site, then open the Microsoft window.
            <button type="button" className="link-btn" onClick={() => void startConnect(pendingAuthUrl)}>
              Open window
            </button>
          </p>
        )}
        {emailError && ui !== 'error' && (
          <p className="inline-error" role="alert">
            {emailError}
          </p>
        )}
      </section>

      <section className="editor-section" aria-labelledby="sources-heading">
        <h2 id="sources-heading">Sources</h2>
        <p className="muted">Turn Greenhouse and Lever on or off. Job Feed source chips save the same setting. Add a public board token or company URL, or remove a board that should no longer be crawled.</p>
        {(['greenhouse', 'lever'] as const).map((name) => {
          const enabledKey = name === 'greenhouse' ? 'greenhouseEnabled' : 'leverEnabled'
          const configured = sourceConfigured(name)
          const enabled = Boolean(doc?.sources[enabledKey]) && configured
          const status = name === 'greenhouse' ? ghStatus : leverStatus
          const addStatus = name === 'greenhouse' ? ghAddStatus : leverAddStatus
          const boardValue = name === 'greenhouse' ? ghBoard : leverBoard
          const setBoard = name === 'greenhouse' ? setGhBoard : setLeverBoard
          const label = name === 'greenhouse' ? 'Greenhouse' : 'Lever'
          const sourceRow = sourceStatus.find((item) => item.source === name)
          const boards = sourceRow?.boards || []
          return (
            <div key={name}>
              <div className={`source-row ${configured ? '' : 'is-unconfigured'}`}>
                <div>
                  <div className="phase-name">{label}</div>
                  <div className="muted">Public job board listings</div>
                </div>
                <label className={`toggle ${configured ? '' : 'is-disabled'}`} title={configured ? undefined : 'Not configured'}>
                  <span className="sr-only">{label}</span>
                  <input
                    type="checkbox"
                    checked={enabled}
                    disabled={!configured}
                    onChange={(event) => void saveSource(enabledKey, event.target.checked)}
                  />
                  <span>{enabled ? 'On' : 'Off'}</span>
                </label>
                <span className="save-status" aria-live="polite">
                  {status === 'saving' && 'Saving…'}
                  {status === 'saved' && 'Saved'}
                </span>
              </div>
              {boards.length > 0 && (
                <ul className="source-board-list">
                  {boards.map((item) => {
                    const busyKey = `${name}:${item.tenantKey}`
                    const busy = removingKey === busyKey || retryingKey === busyKey
                    const boardError = sourceRow
                      ? boardErrorCopy(item, sourceRow, boards.length)
                      : (item.errorMessage || '').trim() || null
                    return (
                      <li key={item.tenantKey} className={`source-board-row${boardError ? ' has-error' : ''}`}>
                        <div className="source-board-copy">
                          <span>
                            <span className="sr-only">{label} board </span>
                            <code>{item.tenantKey}</code>
                          </span>
                          {boardError && (
                            <p className="inline-error" role="alert">
                              {boardError}
                            </p>
                          )}
                        </div>
                        <div className="source-board-actions">
                          <button
                            type="button"
                            className="link-btn"
                            disabled={busy || removingKey !== null || retryingKey !== null}
                            aria-label={`Retry ${label} board ${item.tenantKey}`}
                            onClick={() => void retryBoard(name, item.tenantKey)}
                          >
                            {retryingKey === busyKey ? 'Retrying…' : 'Retry'}
                          </button>
                          <button
                            type="button"
                            className="link-btn danger"
                            disabled={busy || removingKey !== null || retryingKey !== null}
                            aria-label={`Remove ${label} board ${item.tenantKey}`}
                            onClick={() => setConfirmRemove({ name, tenantKey: item.tenantKey })}
                          >
                            {removingKey === busyKey ? 'Removing…' : 'Remove'}
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
              {!configured && (
                <div className="oauth-unconfigured source-unconfigured" role="status">
                  <p>
                    <span className="status-badge status-needs-review">Not configured</span>
                  </p>
                  <p>{sourceUnconfiguredCopy(name)}</p>
                </div>
              )}
              <form
                className="source-add-form"
                onSubmit={(event) => {
                  event.preventDefault()
                  void addBoard(name)
                }}
              >
                <label>
                  {label} board
                  <input
                    value={boardValue}
                    onChange={(event) => setBoard(event.target.value)}
                    placeholder={boardInputHint(name)}
                    autoComplete="off"
                    spellCheck={false}
                    aria-label={`Add ${label} board`}
                  />
                </label>
                <button type="submit" className="secondary" disabled={addStatus === 'saving' || !boardValue.trim()}>
                  {addStatus === 'saving' ? 'Adding…' : configured ? 'Add board' : 'Add and enable'}
                </button>
                <span className="save-status" aria-live="polite">
                  {addStatus === 'saved' && 'Saved'}
                </span>
              </form>
            </div>
          )
        })}
        {sourceError && (
          <div>
            <p className="inline-error" role="alert">
              {sourceError}
            </p>
            {sourceRetry && (
              <button type="button" className="primary" onClick={() => void saveSource(sourceRetry.key, sourceRetry.value)}>
                Retry
              </button>
            )}
          </div>
        )}
      </section>

      <section className="editor-section" aria-labelledby="linkedin-heading">
        <h2 id="linkedin-heading">LinkedIn</h2>
        <p className="muted">
          Guest job search and Easy Apply. Live sockets stay behind LINKEDIN_LIVE (currently {linkedinLive ? 'on' : 'off'}).
          Paste the operator `li_at` cookie — AJAS seals it and never shows it again. Captcha is never bypassed.
        </p>
        <label>
          Account id
          <input
            value={linkedinAccountId}
            onChange={(event) => setLinkedinAccountId(saveLinkedInAccountId(event.target.value))}
            aria-label="LinkedIn account id"
            autoComplete="off"
          />
        </label>
        <label>
          Session cookie (li_at)
          <input
            type="password"
            value={linkedinToken}
            onChange={(event) => setLinkedinToken(event.target.value)}
            aria-label="LinkedIn li_at cookie"
            autoComplete="off"
            placeholder="li_at=…; JSESSIONID=ajax:…"
          />
        </label>
        <div className="modal-actions">
          <button
            type="button"
            className="primary"
            disabled={linkedinBusy || !linkedinToken.trim()}
            onClick={() => {
              setLinkedinBusy(true)
              setLinkedinError(null)
              void liveLinkedInApi
                .putSession(linkedinAccountId, linkedinToken)
                .then((row) => {
                  setLinkedinAccounts((prev) => {
                    const rest = prev.filter((item) => item.accountId !== row.accountId)
                    return [row, ...rest]
                  })
                  setLinkedinToken('')
                  toast('LinkedIn session sealed')
                })
                .catch((err) => setLinkedinError(err instanceof Error ? err.message : 'Could not save LinkedIn session'))
                .finally(() => setLinkedinBusy(false))
            }}
          >
            {linkedinBusy ? 'Saving…' : 'Save session'}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={linkedinBusy}
            onClick={() => {
              setLinkedinBusy(true)
              void liveLinkedInApi
                .revokeSession(linkedinAccountId)
                .then((row) => {
                  setLinkedinAccounts((prev) => prev.map((item) => (item.accountId === row.accountId ? row : item)))
                  toast('LinkedIn session revoked')
                })
                .catch((err) => setLinkedinError(err instanceof Error ? err.message : 'Could not revoke LinkedIn session'))
                .finally(() => setLinkedinBusy(false))
            }}
          >
            Revoke
          </button>
        </div>
        {linkedinError && (
          <p className="inline-error" role="alert">
            {linkedinError}
          </p>
        )}
        {linkedinAccounts.length ? (
          <ul>
            {linkedinAccounts.map((row) => (
              <li key={row.accountId}>
                <code>{row.accountId}</code> {row.status}
                {row.remainingSeconds != null ? ` · ${row.remainingSeconds}s left` : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No LinkedIn sessions yet. Easy Apply needs an active session; guest search does not.</p>
        )}
      </section>

      <section className="editor-section" aria-labelledby="session-heading">
        <h2 id="session-heading">Devices and sessions</h2>
        <p className="muted">Short-lived access tokens with rotating refresh. Dev Bearer user ids still work. Cookie sessions send an HttpOnly `ajas_sess` cookie; writes also send the CSRF token.</p>
        {authConfig?.mode === 'aad' && (
          <p className="banner">
            This host expects an Azure AD JWT.
            {authConfig.loginUrl ? (
              <>
                {' '}
                <a href={authConfig.loginUrl}>Sign in with Microsoft</a>
              </>
            ) : (
              ' Set MICROSOFT_CLIENT_ID and AUTH_JWT_SECRET or AUTH_JWT_JWKS_URL, then reload.'
            )}
          </p>
        )}
        <button
          type="button"
          className="secondary"
          disabled={sessionBusy}
          onClick={() => {
            setSessionBusy(true)
            void request('/api/v1/auth/session', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ label: 'Cursor desktop' }),
            })
              .then((resp) => json<{ deviceId: string; csrfToken?: string }>(resp))
              .then((issued) =>
                request('/api/v1/auth/devices')
                  .then((resp) => json<{ items: { id: string; label: string; createdAt: string; lastSeenAt: string }[] }>(resp))
                  .then((page) => {
                    setDevices(page.items)
                    toast(`Session device ${issued.deviceId.slice(0, 8)}…`)
                  }),
              )
              .catch((err) => toast(err instanceof Error ? err.message : 'Could not issue session', 'error'))
              .finally(() => setSessionBusy(false))
          }}
        >
          Issue session
        </button>
        {devices.length === 0 ? (
          <p className="muted">No session devices yet.</p>
        ) : (
          <ul className="audit-list">
            {devices.map((item) => (
              <li key={item.id}>
                <strong>{item.label}</strong>
                <span className="muted">
                  {' '}
                  {formatWhen(item.lastSeenAt)} · created {formatWhen(item.createdAt)}
                </span>
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    void request(`/api/v1/auth/devices/${encodeURIComponent(item.id)}`, { method: 'DELETE' }).then(() =>
                      setDevices((prev) => prev.filter((row) => row.id !== item.id)),
                    )
                  }}
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="editor-section" aria-labelledby="audit-heading">
        <h2 id="audit-heading">Settings audit trail</h2>
        <p className="muted">Who changed threshold, sources, Auto-Apply, or email connection — and when.</p>
        {auditItems.length > 0 && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              const csv = exportAuditCsv(
                auditItems.map((item) => ({
                  at: item.createdAt,
                  actor: item.actorId,
                  action: item.entityType,
                  target: item.fieldMask.join('|'),
                })),
              )
              const blob = new Blob([csv], { type: 'text/csv' })
              const url = URL.createObjectURL(blob)
              const link = document.createElement('a')
              link.href = url
              link.download = 'ajas-settings-audit.csv'
              link.click()
              URL.revokeObjectURL(url)
            }}
          >
            Export CSV
          </button>
        )}
        {auditItems.length === 0 ? (
          <p className="muted">No audited changes yet.</p>
        ) : (
          <ul className="audit-list">
            {auditItems.slice(0, 20).map((item) => (
              <li key={item.id}>
                <strong>{item.fieldMask.join(', ') || item.entityType}</strong>
                <span className="muted">
                  {' '}
                  {item.actorId} · {formatWhen(item.createdAt)}
                </span>
                <pre className="audit-diff">{JSON.stringify(item.detail, null, 2)}</pre>
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirmRemove && (
        <Modal
          title={`Remove ${sourceTitle(confirmRemove.name)} board?`}
          onClose={() => setConfirmRemove(null)}
        >
          <p>
            Remove <strong>{confirmRemove.tenantKey}</strong> from {sourceTitle(confirmRemove.name)}. Job Feed
            stops listing jobs from this board.
            {(sourceStatus.find((item) => item.source === confirmRemove.name)?.boards || []).length <= 1
              ? ` ${sourceTitle(confirmRemove.name)} goes back to Not configured.`
              : ''}
          </p>
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={() => setConfirmRemove(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => void removeBoard(confirmRemove.name, confirmRemove.tenantKey)}
            >
              Remove board
            </button>
          </div>
        </Modal>
      )}

      {confirmDisconnect && (
        <Modal title="Disconnect Microsoft 365?" onClose={() => setConfirmDisconnect(false)}>
          <p>
            This stops future email ingestion. Mail already imported stays in AJAS. Tokens stored for this app are
            cleared here; Microsoft is not contacted.
          </p>
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={() => setConfirmDisconnect(false)}>
              Cancel
            </button>
            <button type="button" className="danger" onClick={() => void disconnect()}>
              Disconnect
            </button>
          </div>
        </Modal>
      )}

      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
    </div>
  )
}
