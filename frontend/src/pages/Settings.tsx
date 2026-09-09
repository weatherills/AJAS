import { useCallback, useEffect, useRef, useState } from 'react'
import { getUserId, learningApi, setUserId, settingsApi, USE_MOCK } from '../api'
import type { SettingsDoc } from '../api/settingsTypes'
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
  OAUTH_MESSAGE_TYPE,
  percentToApi,
  previewCopy,
  SLIDER_MAX,
  SLIDER_MIN,
  SLIDER_STEP,
} from '../lib/settings'
import { LearningPanel } from './Learning'

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

export function SettingsPage() {
  const [userId, setUser] = useState(getUserId())
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
  const [connecting, setConnecting] = useState(false)
  const [popupBlocked, setPopupBlocked] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [pendingAuthUrl, setPendingAuthUrl] = useState<string | null>(null)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [tuningMode, setTuningMode] = useState<'auto' | 'manual'>('auto')
  const [strictness, setStrictness] = useState<0 | 1 | 2>(1)
  const [learningError, setLearningError] = useState<string | null>(null)
  const [learningSample, setLearningSample] = useState(0)
  const [learningStatus, setLearningStatus] = useState<SaveStatus>('idle')
  const [learningTick, setLearningTick] = useState(0)
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
  }, [])

  const load = useCallback(async () => {
    try {
      applyDoc(await settingsApi.get())
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
      toast('Preferences updated. Takes effect on new suggestions.')
    } catch {
      setLearningStatus('error')
      setLearningError('Couldn’t save matching preferences. Try again.')
    }
  }

  async function saveSource(key: 'greenhouseEnabled' | 'leverEnabled', value: boolean) {
    if (!doc) return
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
    } catch {
      setDoc({ ...doc, sources: { ...doc.sources, [key]: previous } })
      setStatus('error')
      setSourceError('Couldn’t save source toggle. Try again.')
      setSourceRetry({ key, value })
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
  const ui = emailUiState(email?.status ?? 'disconnected', email?.errorCode, connecting)

  return (
    <div className="page library-page">
      <header className="library-header">
        <div>
          <a href="#/" className="back-link">
            Home
          </a>
          <h1>Settings</h1>
          <p className="tagline">Match threshold, learning, Microsoft 365 email, and job sources.</p>
        </div>
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
        <p className="muted">Read-only access to your mailbox (Mail.Read and offline_access).</p>
        {ui === 'disconnected' && (
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
              <button type="button" onClick={() => void startConnect()}>
                Reconnect
              </button>
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
        <p className="muted">Turn ingestion on or off. Credentials are not entered here.</p>
        <div className="source-row">
          <div>
            <div className="phase-name">Greenhouse</div>
            <div className="muted">Public job board listings</div>
          </div>
          <label className="toggle">
            <span className="sr-only">Greenhouse</span>
            <input
              type="checkbox"
              checked={Boolean(doc?.sources.greenhouseEnabled)}
              onChange={(event) => void saveSource('greenhouseEnabled', event.target.checked)}
            />
            <span>{doc?.sources.greenhouseEnabled ? 'On' : 'Off'}</span>
          </label>
          <span className="save-status" aria-live="polite">
            {ghStatus === 'saving' && 'Saving…'}
            {ghStatus === 'saved' && 'Saved'}
          </span>
        </div>
        <div className="source-row">
          <div>
            <div className="phase-name">Lever</div>
            <div className="muted">Public job board listings</div>
          </div>
          <label className="toggle">
            <span className="sr-only">Lever</span>
            <input
              type="checkbox"
              checked={Boolean(doc?.sources.leverEnabled)}
              onChange={(event) => void saveSource('leverEnabled', event.target.checked)}
            />
            <span>{doc?.sources.leverEnabled ? 'On' : 'Off'}</span>
          </label>
          <span className="save-status" aria-live="polite">
            {leverStatus === 'saving' && 'Saving…'}
            {leverStatus === 'saved' && 'Saved'}
          </span>
        </div>
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
