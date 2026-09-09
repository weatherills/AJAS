import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { resumeApi } from '../api'
import type { Contact, Education, Experience, ResumeDetail } from '../api/resumeTypes'
import { Modal } from '../components/Modal'
import { StatusBadge } from '../components/StatusBadge'
import { ToastStack } from '../components/Toast'
import { isRunInProgress } from '../lib/runLock'
import { uiStatus } from '../lib/status'
import { editorIsReady, validateEditor, type EditorState } from '../lib/validation'

function emptyContact(): Contact {
  return { fullName: '', email: '', phone: '', location: '', linkedinUrl: '' }
}

function emptyExperience(): Experience {
  return { title: '', company: '', location: '', startDate: '', endDate: '', isCurrent: false, description: '' }
}

function emptyEducation(): Education {
  return { institution: '', degree: '', field: '', startDate: '', endDate: '', isCurrent: false, notes: '' }
}

function editorState(detail: ResumeDetail): EditorState {
  return {
    contact: { ...emptyContact(), ...(detail.contact ?? {}) },
    skills: [...detail.skills],
    experience: detail.experience.map((item) => ({ ...item })),
    education: detail.education.map((item) => ({ ...item })),
  }
}

function snapshot(state: EditorState) {
  return JSON.stringify(state)
}

export function ResumeEditor({ resumeId, onBack, onSaved }: { resumeId: string; onBack: () => void; onSaved: () => void }) {
  const [detail, setDetail] = useState<ResumeDetail | null>(null)
  const [state, setState] = useState<EditorState | null>(null)
  const [baseline, setBaseline] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toasts, setToasts] = useState<{ id: number; text: string; tone?: 'info' | 'error' }[]>([])
  const [blurred, setBlurred] = useState<Record<string, boolean>>({})
  const [saveAttempted, setSaveAttempted] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const toastId = useRef(1)
  const pendingNav = useRef<(() => void) | null>(null)

  const dirty = Boolean(state && snapshot(state) !== baseline)
  const errors = useMemo(() => (state ? validateEditor(state) : {}), [state])
  const showError = (key: string) => (saveAttempted || blurred[key]) && errors[key]

  const toast = (text: string, tone: 'info' | 'error' = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await resumeApi.get(resumeId)
      const nextState = editorState(next)
      setDetail(next)
      setState(nextState)
      setBaseline(snapshot(nextState))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resume')
    } finally {
      setLoading(false)
    }
  }, [resumeId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  const tryNav = (fn: () => void) => {
    if (!dirty) {
      fn()
      return
    }
    pendingNav.current = fn
    setConfirmLeave(true)
  }

  const save = async () => {
    if (!detail || !state) return
    setSaveAttempted(true)
    if (Object.keys(errors).length) {
      setError('Fix the highlighted fields before saving.')
      return
    }
    if (isRunInProgress(detail.id)) {
      setError('This resume is locked by an in-progress apply run.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const contact = {
        ...state.contact,
        linkedinUrl: (state.contact.linkedinUrl?.trim() || '').replace(/^https:\/\/$/i, '') || undefined,
      }
      const updated = await resumeApi.patch(detail.id, { ...state, contact })
      const nextState = editorState(updated)
      setDetail(updated)
      setState(nextState)
      setBaseline(snapshot(nextState))
      toast('Saved')
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p>Loading editor…</p>
  if (!detail || !state) return <p className="inline-error">{error ?? 'Resume not found'}</p>

  const status = uiStatus(detail)
  const highlightMissing = status === 'Needs review'
  const contact = state.contact
  const locked = isRunInProgress(detail.id)

  const setContact = (patch: Partial<Contact>) => setState({ ...state, contact: { ...contact, ...patch } })

  return (
    <div className="page editor-page">
      <header className="page-header">
        <div>
          <button type="button" className="link-btn" onClick={() => tryNav(onBack)}>
            ← Back to library
          </button>
          <h1>Edit resume</h1>
          <p className="muted filename">{detail.fileName}</p>
        </div>
        <StatusBadge status={status} />
      </header>

      {error && <p className="inline-error">{error}</p>}
      {dirty && <p className="unsaved-banner">You have unsaved changes</p>}
      {highlightMissing && (
        <p className="warn-text">This resume needs review. Highlighted fields are required before it can be Ready.</p>
      )}
      {locked && <p className="inline-error">This resume is locked by an in-progress apply run.</p>}

      <section className={`editor-section ${highlightMissing && errors['contact.fullName'] ? 'needs-attn' : ''}`}>
        <h2>Profile</h2>
        <label>
          Full name
          <input
            value={contact.fullName ?? ''}
            onChange={(event) => setContact({ fullName: event.target.value })}
            onBlur={() => setBlurred((prev) => ({ ...prev, 'contact.fullName': true }))}
            aria-invalid={Boolean(showError('contact.fullName'))}
          />
        </label>
        {showError('contact.fullName') && <p className="field-error">{errors['contact.fullName']}</p>}
        <div className="two-col">
          <label>
            Email
            <input
              type="email"
              value={contact.email ?? ''}
              onChange={(event) => setContact({ email: event.target.value })}
              onBlur={() => setBlurred((prev) => ({ ...prev, 'contact.email': true }))}
              aria-invalid={Boolean(showError('contact.email'))}
            />
          </label>
          <label>
            Phone
            <input
              value={contact.phone ?? ''}
              onChange={(event) => setContact({ phone: event.target.value })}
              onBlur={() => setBlurred((prev) => ({ ...prev, 'contact.phone': true }))}
              aria-invalid={Boolean(showError('contact.phone'))}
            />
          </label>
        </div>
        {showError('contact.email') && <p className="field-error">{errors['contact.email']}</p>}
        {showError('contact.phone') && <p className="field-error">{errors['contact.phone']}</p>}
        <label>
          Location
          <input value={contact.location ?? ''} onChange={(event) => setContact({ location: event.target.value })} />
        </label>
        <label>
          LinkedIn URL
          <input
            value={contact.linkedinUrl ?? ''}
            onChange={(event) => setContact({ linkedinUrl: event.target.value })}
            onBlur={() => setBlurred((prev) => ({ ...prev, 'contact.linkedinUrl': true }))}
            aria-invalid={Boolean(showError('contact.linkedinUrl'))}
            placeholder="https://linkedin.com/in/you"
          />
        </label>
        {showError('contact.linkedinUrl') && <p className="field-error">{errors['contact.linkedinUrl']}</p>}
      </section>

      <section className="editor-section">
        <h2>Skills</h2>
        <SkillTags skills={state.skills} onChange={(skills) => setState({ ...state, skills })} />
        {showError('skills') && <p className="field-error">{errors.skills}</p>}
      </section>

      <section className={`editor-section ${highlightMissing && errors.experience ? 'needs-attn' : ''}`}>
        <h2>Experience</h2>
        {showError('experience') && <p className="field-error">{errors.experience}</p>}
        {state.experience.map((exp, i) => (
          <div key={`exp-${i}`} className="repeat-card">
            <div className="repeat-head">
              <strong>Role {i + 1}</strong>
              <button
                type="button"
                className="link-btn danger"
                onClick={() => setState({ ...state, experience: state.experience.filter((_, idx) => idx !== i) })}
              >
                Remove
              </button>
            </div>
            <div className="two-col">
              <label>
                Title
                <input
                  value={exp.title ?? ''}
                  onChange={(event) => {
                    const experience = [...state.experience]
                    experience[i] = { ...exp, title: event.target.value }
                    setState({ ...state, experience })
                  }}
                />
              </label>
              <label>
                Company
                <input
                  value={exp.company ?? ''}
                  onChange={(event) => {
                    const experience = [...state.experience]
                    experience[i] = { ...exp, company: event.target.value }
                    setState({ ...state, experience })
                  }}
                />
              </label>
            </div>
            <label>
              Location
              <input
                value={exp.location ?? ''}
                onChange={(event) => {
                  const experience = [...state.experience]
                  experience[i] = { ...exp, location: event.target.value }
                  setState({ ...state, experience })
                }}
              />
            </label>
            <div className="two-col">
              <label>
                Start
                <input
                  type="month"
                  value={toMonth(exp.startDate)}
                  onChange={(event) => {
                    const experience = [...state.experience]
                    experience[i] = { ...exp, startDate: event.target.value }
                    setState({ ...state, experience })
                  }}
                />
              </label>
              <label>
                End
                <input
                  type="month"
                  value={toMonth(exp.endDate)}
                  disabled={exp.isCurrent}
                  onChange={(event) => {
                    const experience = [...state.experience]
                    experience[i] = { ...exp, endDate: event.target.value }
                    setState({ ...state, experience })
                  }}
                />
              </label>
            </div>
            {showError(`experience.${i}.endDate`) && <p className="field-error">{errors[`experience.${i}.endDate`]}</p>}
            <label className="checkbox">
              <input
                type="checkbox"
                checked={Boolean(exp.isCurrent)}
                onChange={(event) => {
                  const experience = [...state.experience]
                  experience[i] = { ...exp, isCurrent: event.target.checked, endDate: event.target.checked ? '' : exp.endDate }
                  setState({ ...state, experience })
                }}
              />
              Current role
            </label>
            <label>
              Description
              <textarea
                rows={4}
                value={exp.description ?? ''}
                onChange={(event) => {
                  const experience = [...state.experience]
                  experience[i] = { ...exp, description: event.target.value }
                  setState({ ...state, experience })
                }}
              />
            </label>
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => setState({ ...state, experience: [...state.experience, emptyExperience()] })}>
          Add experience
        </button>
      </section>

      <section className="editor-section">
        <h2>Education</h2>
        {state.education.map((ed, i) => (
          <div key={`ed-${i}`} className="repeat-card">
            <div className="repeat-head">
              <strong>School {i + 1}</strong>
              <button
                type="button"
                className="link-btn danger"
                onClick={() => setState({ ...state, education: state.education.filter((_, idx) => idx !== i) })}
              >
                Remove
              </button>
            </div>
            <label>
              School
              <input
                value={ed.institution ?? ''}
                onChange={(event) => {
                  const education = [...state.education]
                  education[i] = { ...ed, institution: event.target.value }
                  setState({ ...state, education })
                }}
              />
            </label>
            <div className="two-col">
              <label>
                Degree
                <input
                  value={ed.degree ?? ''}
                  onChange={(event) => {
                    const education = [...state.education]
                    education[i] = { ...ed, degree: event.target.value }
                    setState({ ...state, education })
                  }}
                />
              </label>
              <label>
                Field
                <input
                  value={ed.field ?? ''}
                  onChange={(event) => {
                    const education = [...state.education]
                    education[i] = { ...ed, field: event.target.value }
                    setState({ ...state, education })
                  }}
                />
              </label>
            </div>
            <div className="two-col">
              <label>
                Start
                <input
                  type="month"
                  value={toMonth(ed.startDate)}
                  onChange={(event) => {
                    const education = [...state.education]
                    education[i] = { ...ed, startDate: event.target.value }
                    setState({ ...state, education })
                  }}
                />
              </label>
              <label>
                End
                <input
                  type="month"
                  value={toMonth(ed.endDate)}
                  disabled={ed.isCurrent}
                  onChange={(event) => {
                    const education = [...state.education]
                    education[i] = { ...ed, endDate: event.target.value }
                    setState({ ...state, education })
                  }}
                />
              </label>
            </div>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={Boolean(ed.isCurrent)}
                onChange={(event) => {
                  const education = [...state.education]
                  education[i] = { ...ed, isCurrent: event.target.checked, endDate: event.target.checked ? '' : ed.endDate }
                  setState({ ...state, education })
                }}
              />
              In progress
            </label>
            <label>
              Notes
              <textarea
                rows={2}
                value={ed.notes ?? ''}
                onChange={(event) => {
                  const education = [...state.education]
                  education[i] = { ...ed, notes: event.target.value }
                  setState({ ...state, education })
                }}
              />
            </label>
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => setState({ ...state, education: [...state.education, emptyEducation()] })}>
          Add education
        </button>
      </section>

      <footer className="editor-actions">
        <button type="button" className="primary" disabled={saving || locked} onClick={() => void save()}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button type="button" className="secondary" onClick={() => tryNav(onBack)}>
          Cancel
        </button>
        <span className="muted">Validated: {editorIsReady(state) ? 'yes' : 'no'}</span>
      </footer>

      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />

      {confirmLeave && (
        <Modal
          title="Unsaved changes"
          onClose={() => {
            setConfirmLeave(false)
            pendingNav.current = null
          }}
        >
          <p>Leave without saving? Your edits will be lost.</p>
          <div className="modal-actions">
            <button
              type="button"
              className="primary"
              onClick={() => {
                setConfirmLeave(false)
                pendingNav.current?.()
                pendingNav.current = null
              }}
            >
              Leave
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setConfirmLeave(false)
                pendingNav.current = null
              }}
            >
              Stay
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function toMonth(value?: string | null) {
  if (!value) return ''
  return value.slice(0, 7)
}

function SkillTags({ skills, onChange }: { skills: string[]; onChange: (skills: string[]) => void }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const value = draft.trim().replace(/,$/, '')
    if (!value) return
    if (!skills.includes(value)) onChange([...skills, value])
    setDraft('')
  }
  return (
    <div>
      <div className="tag-row">
        {skills.map((skill) => (
          <span key={skill} className="tag">
            {skill}
            <button type="button" aria-label={`Remove ${skill}`} onClick={() => onChange(skills.filter((item) => item !== skill))}>
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="tag-input">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault()
              add()
            }
          }}
          placeholder="Type a skill and press Enter"
        />
        <button type="button" className="secondary" onClick={add}>
          Add
        </button>
      </div>
    </div>
  )
}
