import { useEffect, useRef, useState } from 'react'
import { autoApplyApi, resumeApi } from '../api'
import type { CoverLetterMode, JobSource } from '../api/autoApplyTypes'
import type { ResumeListItem } from '../api/resumeTypes'
import {
  autoApplyDisabledReason,
  copyAnswersText,
  defaultPostingUrl,
  inferJobSource,
  previewCoverLetter,
  sourceBadge,
  vendorFieldPreview,
} from '../lib/autoApply'
import { chooseResume, loadApplyPrefs, saveApplyPrefs } from '../lib/applyPrefs'
import { preselectReady } from '../lib/status'

const FALLBACK_CONTACT = {
  full_name: 'Alex Jobseeker',
  email: 'alex@example.com',
  phone: '+15555550100',
  location: 'Remote',
}

type CoverGen = 'idle' | 'generating' | 'ready' | 'error'

type Props = {
  jobTitle: string
  company: string
  jobId: string
  resumeId: string | null
  postingUrl: string | null
  onClose: () => void
  onSubmitted: (requestId: string, state: string) => void
}

export function ApplyModal({ jobTitle, company, jobId, resumeId, postingUrl, onClose, onSubmitted }: Props) {
  const inferred = inferJobSource(jobId, postingUrl)
  const prefs = loadApplyPrefs()
  const [jobSource, setJobSource] = useState<JobSource>(inferred)
  const [url, setUrl] = useState(postingUrl || defaultPostingUrl(jobId, inferred))
  const [coverMode, setCoverMode] = useState<CoverLetterMode>(prefs.defaultCoverMode)
  const [resumes, setResumes] = useState<ResumeListItem[]>([])
  const [activeResumeId, setActiveResumeId] = useState(resumeId || prefs.defaultResumeId || '')
  const [coverText, setCoverText] = useState('')
  const [coverGen, setCoverGen] = useState<CoverGen>('idle')
  const [coverFileError, setCoverFileError] = useState<string | null>(null)
  const [consent, setConsent] = useState(false)
  const [fallback, setFallback] = useState(inferred === 'manual')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [contact, setContact] = useState({ ...FALLBACK_CONTACT, location: prefs.location || FALLBACK_CONTACT.location })
  const firstRef = useRef<HTMLSelectElement | null>(null)

  useEffect(() => {
    firstRef.current?.focus()
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        const items = await resumeApi.list()
        setResumes(items)
        const userActive = await resumeApi.getUserActive().catch(() => null)
        const chosen =
          chooseResume(items, resumeId || userActive?.id || prefs.defaultResumeId || null) ||
          preselectReady(items)
        if (chosen) setActiveResumeId(chosen)
      } catch {
        setResumes([])
      }
    })()
  }, [resumeId, prefs.defaultResumeId])

  useEffect(() => {
    const id = activeResumeId || resumeId
    if (!id) return
    void resumeApi
      .get(id)
      .then((detail) => {
        setContact({
          full_name: detail.contact?.fullName?.trim() || FALLBACK_CONTACT.full_name,
          email: detail.contact?.email?.trim() || FALLBACK_CONTACT.email,
          phone: detail.contact?.phone?.trim() || FALLBACK_CONTACT.phone,
          location: detail.contact?.location?.trim() || prefs.location || FALLBACK_CONTACT.location,
        })
      })
      .catch(() => setContact({ ...FALLBACK_CONTACT, location: prefs.location || FALLBACK_CONTACT.location }))
  }, [activeResumeId, resumeId, prefs.location])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const programmatic = jobSource !== 'manual' && !fallback
  const badge = sourceBadge(jobSource)
  const mapped = vendorFieldPreview(fallback ? 'manual' : jobSource, contact)
  const posting = fallback && !url.toLowerCase().includes('captcha') ? `${url}${url.includes('?') ? '&' : '?'}captcha=1` : url
  const blocked = autoApplyDisabledReason({ resumeId: activeResumeId || resumeId, jobId })
  const generateBlocked = coverMode === 'generate' && coverGen !== 'ready'
  const uploadBlocked = coverMode === 'upload' && !coverText.trim()

  const generateLetter = async () => {
    setCoverGen('generating')
    setCoverFileError(null)
    try {
      const preview = await autoApplyApi.previewCoverLetter({
        job_source: jobSource,
        job_posting_id: jobId,
        posting_url: posting,
        resume_id: activeResumeId || resumeId || undefined,
        answers: contact,
        match_explanation: `${jobTitle} at ${company}`,
      })
      setCoverText(preview.text)
      setCoverGen('ready')
    } catch {
      setCoverText(
        previewCoverLetter({
          name: contact.full_name,
          jobTitle,
          company,
          source: jobSource,
          postingUrl: posting,
        }),
      )
      setCoverGen('ready')
    }
  }

  const submit = async () => {
    if (blocked) {
      setError(blocked)
      return
    }
    if (!consent) {
      setError('Confirm consent before submitting.')
      return
    }
    if (coverMode === 'upload' && !coverText.trim()) {
      setError('Upload a cover letter or switch to generate/none.')
      return
    }
    if (coverMode === 'generate' && coverGen !== 'ready') {
      setError('Generate a cover letter, or switch the cover letter mode to none.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await autoApplyApi.create({
        job_source: fallback ? 'manual' : jobSource,
        job_posting_id: jobId,
        posting_url: posting,
        resume_id: activeResumeId || resumeId || 'resume-active',
        cover_letter_mode: coverMode === 'generate' && coverText.trim() ? 'upload' : coverMode,
        cover_letter_text: coverMode === 'none' ? undefined : coverText,
        consent_approved: true,
        answers: {
          full_name: contact.full_name,
          email: contact.email,
          phone: contact.phone,
          location: contact.location,
        },
      })
      onSubmitted(created.request_id, created.state)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit this application')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal apply-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="apply-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="apply-modal-title">Auto-Apply</h2>
        <p className="muted">
          {jobTitle} at {company}
        </p>
        <p>
          <span className={`status-badge status-${jobSource}`}>{badge.label}</span>{' '}
          {programmatic ? 'Programmatic submit available' : 'Manual package — CAPTCHA or unsupported source'}
        </p>
        <label>
          Resume / profile version
          <select
            value={activeResumeId}
            onChange={(event) => {
              const nextId = event.target.value
              setActiveResumeId(nextId)
              saveApplyPrefs({ ...prefs, defaultResumeId: nextId })
            }}
            aria-label="Resume version for this apply"
          >
            {(resumes.length
              ? resumes.map((item) => ({ id: item.id, fileName: item.fileName }))
              : activeResumeId
                ? [{ id: activeResumeId, fileName: activeResumeId }]
                : []
            ).map((item) => (
              <option key={item.id} value={item.id}>
                {item.fileName}
              </option>
            ))}
          </select>
        </label>
        <label>
          Job source
          <select ref={firstRef} value={jobSource} onChange={(event) => setJobSource(event.target.value as JobSource)}>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="manual">Manual package</option>
          </select>
        </label>
        <label>
          Posting URL
          <input value={url} onChange={(event) => setUrl(event.target.value)} />
        </label>
        <label>
          Cover letter
          <select
            value={coverMode}
            onChange={(event) => {
              const next = event.target.value as CoverLetterMode
              setCoverMode(next)
              saveApplyPrefs({ ...prefs, defaultCoverMode: next })
              if (next !== 'generate') setCoverGen('idle')
            }}
          >
            <option value="none">None</option>
            <option value="generate">Generate tailored letter</option>
            <option value="upload">Upload a letter</option>
          </select>
        </label>
        {coverMode === 'generate' && (
          <section className="apply-cover-gen" aria-live="polite">
            {coverGen === 'generating' && <p className="muted">Generating cover letter…</p>}
            {coverGen === 'error' && <p className="inline-error">Could not generate. You can still submit without a letter.</p>}
            {(coverGen === 'ready' || coverText) && coverGen !== 'generating' && (
              <label>
                Cover letter (editable)
                <textarea
                  rows={8}
                  value={coverText}
                  onChange={(event) => setCoverText(event.target.value)}
                  aria-label="Generated cover letter"
                />
              </label>
            )}
            <button type="button" className="secondary" disabled={coverGen === 'generating'} onClick={() => void generateLetter()}>
              {coverGen === 'ready' ? 'Regenerate' : coverGen === 'generating' ? 'Generating…' : 'Generate cover letter'}
            </button>
          </section>
        )}
        {coverMode === 'upload' && (
          <>
            <label>
              Cover letter file
              <input
                type="file"
                accept=".txt,.md,.pdf,.doc,.docx,text/plain"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  setCoverFileError(null)
                  if (!file) return
                  if (file.size > 200_000) {
                    setCoverFileError('Cover letter must be under 200 KB.')
                    return
                  }
                  void (async () => {
                    try {
                      const name = file.name.toLowerCase()
                      const textual =
                        name.endsWith('.txt') ||
                        name.endsWith('.md') ||
                        file.type.startsWith('text/')
                      const text = textual ? (await file.text()).trim() : (await autoApplyApi.extractCoverLetter(file)).trim()
                      if (!text) {
                        setCoverFileError('Could not read that file as text. Try a .txt letter or paste it below.')
                        return
                      }
                      setCoverText(text)
                    } catch (err) {
                      setCoverFileError(err instanceof Error ? err.message : 'Could not read that file.')
                    }
                  })()
                }}
              />
            </label>
            <label>
              Or paste the letter
              <textarea
                rows={6}
                value={coverText}
                placeholder="Paste a short cover letter"
                onChange={(event) => {
                  setCoverFileError(null)
                  setCoverText(event.target.value)
                }}
              />
            </label>
          </>
        )}
        {coverFileError && <p className="inline-error">{coverFileError}</p>}
        {coverMode === 'upload' && coverText && <p className="muted">Uploaded {coverText.trim().split(/\s+/).length} words.</p>}
        <label className="apply-check">
          <input type="checkbox" checked={fallback} onChange={(event) => setFallback(event.target.checked)} />
          This posting has a CAPTCHA or SSO wall
        </label>
        <section className="apply-preview" aria-label="Autofill preview">
          <h3>Mapped fields ({programmatic ? badge.label : 'manual'})</h3>
          {mapped.map((row) => (
            <p key={row.label}>
              <strong>{row.label}</strong> {row.value || '—'}
            </p>
          ))}
          <p>
            <strong>Resume</strong> {activeResumeId || resumeId || 'resume-active'}
          </p>
          {!programmatic && (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                void navigator.clipboard?.writeText(copyAnswersText(mapped))
                setCopied(true)
                window.setTimeout(() => setCopied(false), 2000)
              }}
            >
              {copied ? 'Copied answers' : 'Copy answers'}
            </button>
          )}
        </section>
        <label className="apply-check">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          I authorize AJAS to submit this application with the data shown
        </label>
        {blocked && <p className="inline-error">{blocked}</p>}
        {error && <p className="inline-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            title={blocked || undefined}
            onClick={() => void submit()}
            disabled={saving || !consent || Boolean(blocked) || generateBlocked || uploadBlocked}
          >
            {saving ? 'Submitting…' : programmatic ? 'Submit application' : 'Build package'}
          </button>
        </div>
      </div>
    </div>
  )
}
