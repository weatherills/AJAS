import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { emailApi, jobsApi } from '../api'
import type { EmailMessage, EmailSuggestion, EmailTemplate, EmailThread } from '../api/emailTypes'
import type { JobCard } from '../api/jobsTypes'
import { JobCrossLinks } from './JobCrossLinks'
import { Modal } from './Modal'
import { ToastStack } from './Toast'
import {
  fileSize,
  fillTemplate,
  leftoverVars,
  previewable,
  relativeTime,
  threadVariables,
  validateAttachments,
} from '../lib/email'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function EmailThreadPane({
  thread,
  onThreadChange,
  compact = false,
}: {
  thread: EmailThread
  onThreadChange?: (thread: EmailThread) => void
  compact?: boolean
}) {
  const [messages, setMessages] = useState<EmailMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [templateId, setTemplateId] = useState('')
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<EmailSuggestion[]>([])
  const [suggestError, setSuggestError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [linkOpen, setLinkOpen] = useState(false)
  const [unlinkOpen, setUnlinkOpen] = useState(false)
  const [jobs, setJobs] = useState<JobCard[]>([])
  const [jobQuery, setJobQuery] = useState('')
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(1)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)

  const toast = (text: string, tone: Toast['tone'] = 'info') => {
    const id = toastId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 5000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const page = await emailApi.listMessages(thread.id)
      setMessages(page.items)
      onThreadChange?.(page.thread)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load messages')
    } finally {
      setLoading(false)
    }
  }, [thread.id, onThreadChange])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void emailApi.templates().then(setTemplates).catch(() => setTemplates([]))
  }, [])

  const vars = useMemo(
    () => threadVariables({ ...thread, participants: thread.participants || [] }),
    [thread],
  )
  const leftovers = leftoverVars(body)
  const subject = thread.subject.toLowerCase().startsWith('re:') ? thread.subject : `Re: ${thread.subject}`
  const lastInbound = [...messages].reverse().find((item) => item.isIncoming)
  const toLine = lastInbound?.from.address || thread.participants?.[0] || ''

  async function send() {
    if (!body.trim() || leftovers.length) return
    setSending(true)
    try {
      const sent = await emailApi.reply(thread.id, {
        bodyText: body,
        idempotencyKey: `${thread.id}-${Date.now()}`,
        attachments: files.map((file) => ({
          fileName: file.name,
          contentType: file.type || 'application/octet-stream',
          size: file.size,
        })),
      })
      setMessages((prev) => [...prev, sent])
      setBody('')
      setFiles([])
      setSuggestions([])
      toast('Sent')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not send', 'error')
    } finally {
      setSending(false)
    }
  }

  async function generate() {
    setSuggestError(null)
    try {
      setSuggestions(await emailApi.suggestions(thread.id, { tone: 'professional' }))
    } catch (err) {
      const message =
        err instanceof Error && (err.message.toLowerCase().includes('limit') || err.message.toLowerCase().includes('rate'))
          ? 'Suggestion limit reached for today. Try again tomorrow.'
          : err instanceof Error
            ? err.message
            : 'Could not generate replies'
      setSuggestError(message)
    }
  }

  async function openLink() {
    setLinkOpen(true)
    try {
      const page = await jobsApi.list({
        sources: ['greenhouse', 'lever'],
        q: jobQuery,
        location: '',
        status: 'all',
        limit: 50,
        cursor: null,
      })
      setJobs(page.items)
    } catch {
      setJobs([])
    }
  }

  const filteredJobs = jobs.filter((job) => {
    const blob = `${job.title} ${job.company}`.toLowerCase()
    return !jobQuery || blob.includes(jobQuery.toLowerCase())
  })

  return (
    <div className={`email-pane ${compact ? 'email-pane-compact' : ''}`}>
      <div className="email-pane-head">
        <div>
          <h2>{thread.subject}</h2>
          <p className="muted">
            From: {toLine}
            {thread.linked ? ` · ${thread.jobTitle} at ${thread.jobCompany}` : ''}
          </p>
          {thread.jobId && <JobCrossLinks jobId={thread.jobId} current="email" />}
        </div>
        <div className="email-pane-actions">
          {!thread.linked && (
            <button type="button" className="secondary" onClick={() => void openLink()}>
              Link to job
            </button>
          )}
          {thread.linked && (
            <button type="button" className="secondary" onClick={() => setUnlinkOpen(true)}>
              Unlink from job
            </button>
          )}
        </div>
      </div>
      {!thread.linked && (
        <p className="unlinked-badge" role="status">
          Unlinked
        </p>
      )}
      {loading && <p className="skeleton">Loading messages…</p>}
      {error && <p className="inline-error">{error}</p>}
      <ol className="message-list">
        {messages.map((item) => (
          <li key={item.id} className={`message-card ${item.isIncoming ? 'is-in' : 'is-out'}`}>
            <div className="message-meta">
              <strong>{item.from.name || item.from.address}</strong>
              <span className="muted">{relativeTime(item.receivedAt)}</span>
            </div>
            <p className="message-body">{item.bodyText}</p>
            {item.attachments.length > 0 && (
              <ul className="attach-list">
                {item.attachments.map((file) => (
                  <li key={file.id}>
                    {file.fileName} · {fileSize(file.size)}
                    {file.status === 'skipped_oversize' ? ' (too large)' : ''}
                    {previewable(file.contentType, file.fileName) ? ' · Preview' : ' · Download'}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          void send()
        }}
      >
        <label className="sr-only" htmlFor={`reply-${thread.id}`}>
          Reply
        </label>
        <p className="muted">
          To: {toLine} · Subject: {subject}
        </p>
        <div className="composer-tools">
          <label>
            Template
            <select
              aria-label="Reply template"
              value={templateId}
              onChange={(event) => {
                const next = event.target.value
                setTemplateId(next)
                const found = templates.find((item) => item.id === next)
                if (found) setBody(fillTemplate(found.body, vars))
              }}
            >
              <option value="">Choose a template</option>
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={() => void generate()}>
            Generate reply
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!templateId}
            onClick={() => {
              if (!templateId) return
              void emailApi.previewTemplate(templateId).then((preview) => {
                setPreviewHtml(preview.html)
              }).catch(() => undefined)
            }}
          >
            Preview theme
          </button>
        </div>
        {previewHtml && (
          <iframe title="Email template preview" className="email-preview" sandbox="" srcDoc={previewHtml} />
        )}
        {suggestError && <p className="inline-error">{suggestError}</p>}
        {suggestions.length > 0 && (
          <ul className="suggestion-list">
            {suggestions.map((item) => (
              <li key={item.tone}>
                <button
                  type="button"
                  className="suggestion-card"
                  onClick={() => {
                    setBody(item.text)
                    composerRef.current?.focus()
                  }}
                >
                  <strong>{item.tone}</strong>
                  <span>{item.text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <textarea
          id={`reply-${thread.id}`}
          ref={composerRef}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={compact ? 5 : 8}
          placeholder="Write a reply…"
          required
        />
        {leftovers.length > 0 && <p className="warn-text">Fill template fields: {leftovers.join(', ')}</p>}
        {fileError && <p className="inline-error">{fileError}</p>}
        <div className="composer-files">
          <label className="secondary file-btn">
            Attach
            <input
              type="file"
              multiple
              className="sr-only"
              onChange={(event) => {
                const next = Array.from(event.target.files || [])
                const checked = validateAttachments([...files, ...next])
                setFileError(checked.error)
                if (!checked.error) setFiles(checked.accepted)
                event.target.value = ''
              }}
            />
          </label>
          {files.map((file) => (
            <button
              key={file.name}
              type="button"
              className="chip"
              onClick={() => setFiles((prev) => prev.filter((item) => item !== file))}
            >
              {file.name} ×
            </button>
          ))}
        </div>
        <div className="actions">
          <button type="submit" className="primary" disabled={sending || !body.trim() || leftovers.length > 0}>
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </form>
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
      {linkOpen && (
        <Modal title="Link to job" onClose={() => setLinkOpen(false)}>
          <label>
            Search jobs
            <input value={jobQuery} onChange={(event) => setJobQuery(event.target.value)} />
          </label>
          <ul className="job-pick">
            {filteredJobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const updated = await emailApi.link(thread.id, job.id)
                      onThreadChange?.(updated)
                      toast(`Linked to ${job.title}`)
                      setLinkOpen(false)
                    } catch (err) {
                      toast(err instanceof Error ? err.message : 'Could not link', 'error')
                    }
                  }}
                >
                  {job.title} · {job.company}
                </button>
              </li>
            ))}
          </ul>
        </Modal>
      )}
      {unlinkOpen && (
        <Modal title="Unlink from job" onClose={() => setUnlinkOpen(false)}>
          <p>Remove the link between this thread and {thread.jobTitle || 'the job'}?</p>
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={async () => {
                const updated = await emailApi.unlink(thread.id)
                onThreadChange?.(updated)
                setUnlinkOpen(false)
                toast('Unlinked')
              }}
            >
              Unlink
            </button>
            <button type="button" className="secondary" onClick={() => setUnlinkOpen(false)}>
              Cancel
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
