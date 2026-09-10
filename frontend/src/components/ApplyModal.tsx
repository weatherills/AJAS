import { useEffect, useRef, useState } from 'react'
import { autoApplyApi, resumeApi } from '../api'
import type { CoverLetterMode, JobSource } from '../api/autoApplyTypes'
import { defaultPostingUrl, inferJobSource } from '../lib/autoApply'

const FALLBACK_CONTACT = {
  full_name: 'Alex Jobseeker',
  email: 'alex@example.com',
  phone: '+15555550100',
}

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
  const [jobSource, setJobSource] = useState<JobSource>(inferred)
  const [url, setUrl] = useState(postingUrl || defaultPostingUrl(jobId, inferred))
  const [coverMode, setCoverMode] = useState<CoverLetterMode>('none')
  const [consent, setConsent] = useState(false)
  const [fallback, setFallback] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contact, setContact] = useState(FALLBACK_CONTACT)
  const firstRef = useRef<HTMLSelectElement | null>(null)

  useEffect(() => {
    firstRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!resumeId) return
    void resumeApi
      .get(resumeId)
      .then((detail) => {
        setContact({
          full_name: detail.contact?.fullName?.trim() || FALLBACK_CONTACT.full_name,
          email: detail.contact?.email?.trim() || FALLBACK_CONTACT.email,
          phone: detail.contact?.phone?.trim() || FALLBACK_CONTACT.phone,
        })
      })
      .catch(() => setContact(FALLBACK_CONTACT))
  }, [resumeId])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const programmatic = jobSource !== 'manual' && !fallback
  const posting = fallback && !url.toLowerCase().includes('captcha') ? `${url}${url.includes('?') ? '&' : '?'}captcha=1` : url

  const submit = async () => {
    if (!consent) {
      setError('Confirm consent before submitting.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await autoApplyApi.create({
        job_source: jobSource,
        job_posting_id: jobId,
        posting_url: posting,
        resume_id: resumeId || 'resume-active',
        cover_letter_mode: coverMode,
        consent_approved: true,
        answers: {
          full_name: contact.full_name,
          email: contact.email,
          phone: contact.phone,
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
          <span className={`status-badge status-${jobSource}`}>{jobSource}</span>{' '}
          {programmatic ? 'Programmatic submit available' : 'Manual package — CAPTCHA or unsupported source'}
        </p>
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
          <select value={coverMode} onChange={(event) => setCoverMode(event.target.value as CoverLetterMode)}>
            <option value="none">None</option>
            <option value="generate">Generate tailored letter</option>
          </select>
        </label>
        {coverMode === 'generate' && (
          <p className="muted">AJAS writes a short letter from the posting. Azure OpenAI is used when configured.</p>
        )}
        <label className="apply-check">
          <input type="checkbox" checked={fallback} onChange={(event) => setFallback(event.target.checked)} />
          This posting has a CAPTCHA or SSO wall
        </label>
        <section className="apply-preview" aria-label="Autofill preview">
          <h3>Mapped fields</h3>
          <p>
            <strong>Name</strong> {contact.full_name}
          </p>
          <p>
            <strong>Email</strong> {contact.email}
          </p>
          <p>
            <strong>Phone</strong> {contact.phone}
          </p>
          <p>
            <strong>Resume</strong> {resumeId || 'resume-active'}
          </p>
        </section>
        <label className="apply-check">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          I authorize AJAS to submit this application with the data shown
        </label>
        {error && <p className="inline-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="button" className="primary" onClick={() => void submit()} disabled={saving || !consent}>
            {saving ? 'Submitting…' : programmatic ? 'Submit application' : 'Build package'}
          </button>
        </div>
      </div>
    </div>
  )
}
