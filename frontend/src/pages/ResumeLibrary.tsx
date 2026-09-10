import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getUserId, resumeApi, setUserId, USE_MOCK } from '../api'
import type { ResumeDetail, ResumeListItem } from '../api/resumeTypes'
import { sha256Hex } from '../lib/hash'
import { LAST_READY_KEY, RUN_LOCK_KEY } from '../lib/runLock'
import { canSelectForRun, isParsing, preselectReady, uiStatus } from '../lib/status'
import { validateClientFile } from '../lib/validation'
import { AppNav } from '../components/AppNav'
import { Modal } from '../components/Modal'
import { StatusBadge } from '../components/StatusBadge'
import { ToastStack } from '../components/Toast'
import { reviewHref } from '../lib/routes'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function ResumeLibrary() {
  const [items, setItems] = useState<ResumeListItem[]>([])
  const [details, setDetails] = useState<Record<string, ResumeDetail>>({})
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [error, setError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [preview, setPreview] = useState<{ id: string; tab: 'original' | 'parsed'; url?: string } | null>(null)
  const [duplicate, setDuplicate] = useState<{ file: File; existing: ResumeListItem } | null>(null)
  const [rename, setRename] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<ResumeListItem | null>(null)
  const [applyOpen, setApplyOpen] = useState(false)
  const [runId, setRunId] = useState('run-1')
  const [applyResumeId, setApplyResumeId] = useState('')
  const [userId, setUser] = useState(getUserId())
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const toastId = useRef(1)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000)
  }

  const load = useCallback(async () => {
    try {
      const list = await resumeApi.list()
      setItems(list)
      setError(null)
      const parsing = list.filter((item) => isParsing(item.status))
      if (parsing.length) {
        const extra: Record<string, ResumeDetail> = {}
        for (const item of parsing) {
          extra[item.id] = await resumeApi.get(item.id)
        }
        setDetails((prev) => ({ ...prev, ...extra }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load resumes')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const hasParsing = items.some((item) => isParsing(item.status))
    if (!hasParsing) return
    const handle = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(handle)
  }, [items, load])

  const filtered = useMemo(() => {
    return items
      .filter((item) => {
        const status = uiStatus(item)
        if (query && !item.fileName.toLowerCase().includes(query.toLowerCase())) return false
        if (statusFilter !== 'all' && status !== statusFilter) return false
        if (typeFilter === 'pdf' && !item.fileName.toLowerCase().endsWith('.pdf')) return false
        if (typeFilter === 'docx' && !item.fileName.toLowerCase().endsWith('.docx')) return false
        return true
      })
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  }, [items, query, statusFilter, typeFilter])

  async function doUpload(file: File, force = false) {
    const clientError = validateClientFile(file)
    if (clientError) {
      setUploadError(clientError)
      return
    }
    setUploadError(null)
    if (!force) {
      const hash = await sha256Hex(file)
      const existing = items.find((item) => item.fileHash === hash)
      if (existing) {
        setDuplicate({ file, existing })
        setRename(file.name.replace(/(\.[^.]+)$/, ' copy$1'))
        return
      }
    }
    setBusy(true)
    try {
      await resumeApi.upload(file)
      toast(`${file.name} uploaded`)
      await load()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function openPreview(item: ResumeListItem) {
    const detail = details[item.id] ?? (await resumeApi.get(item.id))
    setDetails((prev) => ({ ...prev, [item.id]: detail }))
    let url: string | undefined
    try {
      url = await resumeApi.previewUrl(item.id)
    } catch {
      url = undefined
    }
    setPreview({ id: item.id, tab: 'parsed', url })
  }

  const lockedId = localStorage.getItem(RUN_LOCK_KEY)
  const applySelected = items.find((item) => item.id === applyResumeId)

  return (
    <div className="page library-page">
      <AppNav />
      <header className="library-header">
        <div>
          <h1>Resume library</h1>
          <p className="tagline">Upload, parse, edit, and pick a resume for an apply run.</p>
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

      {USE_MOCK && <p className="banner">Demo data (mock API). Uploads stay in this browser session.</p>}

      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          const file = event.dataTransfer.files[0]
          if (file) void doUpload(file)
        }}
      >
        <p>Drag a PDF or DOCX here, or</p>
        <button type="button" className="primary" onClick={() => fileRef.current?.click()} disabled={busy}>
          Upload resume
        </button>
        <input
          ref={fileRef}
          className="sr-only"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void doUpload(file)
            event.target.value = ''
          }}
        />
        {busy && <p className="muted">Uploading…</p>}
        {uploadError && <p className="inline-error">{uploadError}</p>}
      </div>

      <div className="toolbar">
        <label>
          Search
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name" />
        </label>
        <label>
          Status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">All</option>
            <option>Queued</option>
            <option>Parsing</option>
            <option>Ready</option>
            <option>Needs review</option>
            <option>Failed</option>
          </select>
        </label>
        <label>
          Type
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="pdf">PDF</option>
            <option value="docx">DOCX</option>
          </select>
        </label>
        <button type="button" onClick={() => void load()}>
          Refresh
        </button>
        <button
          type="button"
          className="primary"
          onClick={() => {
            setApplyResumeId(preselectReady(items))
            setApplyOpen(true)
          }}
        >
          Start apply run
        </button>
      </div>

      {error && (
        <p className="inline-error">
          {error}{' '}
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </p>
      )}

      <div className="table-wrap">
        <table className="resume-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Last updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No resumes yet.
                </td>
              </tr>
            )}
            {filtered.map((item) => {
              const status = uiStatus(item)
              const locked = lockedId === item.id
              return (
                <tr key={item.id}>
                  <td>{item.fileName}</td>
                  <td>{item.fileName.toLowerCase().endsWith('.docx') ? 'DOCX' : 'PDF'}</td>
                  <td>
                    <StatusBadge status={status} />
                    {isParsing(item.status) && <span className="muted"> Still parsing…</span>}
                  </td>
                  <td>{new Date(item.updatedAt).toLocaleString()}</td>
                  <td className="actions">
                    <button type="button" onClick={() => void openPreview(item)}>
                      Preview
                    </button>
                    <a href={`#/resumes/${item.id}/edit`}>Edit</a>
                    {(status === 'Ready' || status === 'Needs review') && (
                      <a href={reviewHref({ resumeId: item.id })}>Matches</a>
                    )}
                    {status === 'Failed' && (
                      <button
                        type="button"
                        onClick={async () => {
                          await resumeApi.retryParse(item.id)
                          toast('Parse re-queued')
                          await load()
                        }}
                      >
                        Retry parse
                      </button>
                    )}
                    {status === 'Needs review' && <a href={`#/resumes/${item.id}/edit`}>Review &amp; fix</a>}
                    <button
                      type="button"
                      disabled={locked}
                      title={locked ? 'This resume is locked by an in-progress apply run' : 'Delete'}
                      onClick={() => setConfirmDelete(item)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {preview && (
        <aside className="preview-panel" aria-label="Resume preview">
          <div className="preview-head">
            <h2>Preview</h2>
            <button type="button" onClick={() => setPreview(null)}>
              Close
            </button>
          </div>
          <div className="tabs" role="tablist">
            <button type="button" role="tab" aria-selected={preview.tab === 'original'} onClick={() => setPreview({ ...preview, tab: 'original' })}>
              Original
            </button>
            <button type="button" role="tab" aria-selected={preview.tab === 'parsed'} onClick={() => setPreview({ ...preview, tab: 'parsed' })}>
              Parsed
            </button>
          </div>
          {preview.tab === 'original' &&
            (preview.url ? (
              <iframe title="Original resume" src={preview.url} className="preview-frame" />
            ) : (
              <p>
                Preview unavailable.{' '}
                {preview.url === undefined && (
                  <button type="button" onClick={() => void openPreview(items.find((i) => i.id === preview.id)!)}>
                    Try download link
                  </button>
                )}
              </p>
            ))}
          {preview.tab === 'parsed' && <ParsedView detail={details[preview.id]} />}
        </aside>
      )}

      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />

      {duplicate && (
        <Modal title="Duplicate resume" onClose={() => setDuplicate(null)}>
          <p>
            This file matches <strong>{duplicate.existing.fileName}</strong>. Keep both (optionally rename) or cancel.
          </p>
          <label>
            File name
            <input value={rename} onChange={(event) => setRename(event.target.value)} />
          </label>
          <div className="modal-actions">
            <button type="button" onClick={() => setDuplicate(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => {
                const renamed = new File([duplicate.file], rename || duplicate.file.name, { type: duplicate.file.type })
                setDuplicate(null)
                void doUpload(renamed, true)
              }}
            >
              Keep both
            </button>
          </div>
        </Modal>
      )}

      {confirmDelete && (
        <Modal title="Delete resume" onClose={() => setConfirmDelete(null)}>
          <p>
            Delete <strong>{confirmDelete.fileName}</strong>? This hides it from the library.
          </p>
          {lockedId === confirmDelete.id && (
            <p className="inline-error">This resume is locked by an in-progress apply run.</p>
          )}
          <div className="modal-actions">
            <button type="button" onClick={() => setConfirmDelete(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="danger"
              disabled={lockedId === confirmDelete.id}
              onClick={async () => {
                await resumeApi.remove(confirmDelete.id)
                setConfirmDelete(null)
                toast('Resume deleted')
                await load()
              }}
            >
              Delete
            </button>
          </div>
        </Modal>
      )}

      {applyOpen && (
        <Modal title="Apply run" onClose={() => setApplyOpen(false)}>
          <p>Choose one resume for this run. Failed, queued, and parsing resumes cannot be selected.</p>
          <label>
            Run id
            <input value={runId} onChange={(event) => setRunId(event.target.value)} />
          </label>
          <fieldset className="resume-choices">
            <legend>Resume</legend>
            {items.map((item) => {
              const status = uiStatus(item)
              const selectable = canSelectForRun(status)
              return (
                <label key={item.id} title={!selectable ? `${status} resumes cannot be selected` : undefined}>
                  <input
                    type="radio"
                    name="apply-resume"
                    disabled={!selectable}
                    checked={applyResumeId === item.id}
                    onChange={() => setApplyResumeId(item.id)}
                  />
                  {item.fileName} <StatusBadge status={status} />
                  {status === 'Needs review' && <span className="muted"> Review before applying.</span>}
                  <button type="button" className="linkish" onClick={() => void openPreview(item)}>
                    Preview
                  </button>
                </label>
              )
            })}
          </fieldset>
          {applySelected && uiStatus(applySelected) === 'Needs review' && (
            <p className="warn-text">This resume still needs review. You can use it, but fix issues first if you can.</p>
          )}
          <div className="modal-actions">
            <button type="button" onClick={() => setApplyOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              disabled={!applyResumeId}
              onClick={async () => {
                await resumeApi.setActive(runId, applyResumeId)
                localStorage.setItem(LAST_READY_KEY, applyResumeId)
                localStorage.setItem(RUN_LOCK_KEY, applyResumeId)
                toast(`Active resume set for ${runId}`)
                setApplyOpen(false)
              }}
            >
              Use this resume
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function ParsedView({ detail }: { detail?: ResumeDetail }) {
  if (!detail) return <p className="muted">Loading parsed view…</p>
  return (
    <div className="parsed-view">
      <h3>{detail.contact?.fullName || detail.fileName}</h3>
      <p>{[detail.contact?.email, detail.contact?.phone, detail.contact?.location].filter(Boolean).join(' · ')}</p>
      <h4>Skills</h4>
      <p>{detail.skills.join(', ') || '—'}</p>
      <h4>Experience</h4>
      <ul>
        {detail.experience.map((item, i) => (
          <li key={i}>
            {item.title} · {item.company} ({item.startDate}–{item.isCurrent ? 'Present' : item.endDate})
          </li>
        ))}
      </ul>
      <h4>Education</h4>
      <ul>
        {detail.education.map((item, i) => (
          <li key={i}>
            {item.institution} · {item.degree}
          </li>
        ))}
      </ul>
    </div>
  )
}
