import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { emailApi, jobsApi } from '../api'
import type { EmailMessage, EmailSuggestion, EmailTemplate, EmailThread } from '../api/emailTypes'
import type { JobCard } from '../api/jobsTypes'
import { JobCrossLinks } from './JobCrossLinks'
import { Modal } from './Modal'
import { ToastStack } from './Toast'
import {
  attachmentKind,
  attachmentKindLabel,
  attachmentNeedsAuthFetch,
  fileSize,
  fillTemplate,
  htmlToPlain,
  insertAtCaret,
  leftoverVars,
  plainToHtml,
  previewable,
  relativeTime,
  sanitizeMailHtml,
  needsSendConfirm,
  threadVariables,
  validateAttachments,
} from '../lib/email'

type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function EmailThreadPane({
  thread,
  fromAddress,
  onThreadChange,
  compact = false,
}: {
  thread: EmailThread
  fromAddress?: string | null
  onThreadChange?: (thread: EmailThread) => void
  compact?: boolean
}) {
  const [messages, setMessages] = useState<EmailMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [composing, setComposing] = useState(false)
  const [plainMode, setPlainMode] = useState(false)
  const [body, setBody] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [templateId, setTemplateId] = useState('')
  const [suggestions, setSuggestions] = useState<EmailSuggestion[]>([])
  const [suggestError, setSuggestError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [fileErrors, setFileErrors] = useState<string[]>([])
  const [linkOpen, setLinkOpen] = useState(false)
  const [unlinkOpen, setUnlinkOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [jobs, setJobs] = useState<JobCard[]>([])
  const [jobQuery, setJobQuery] = useState('')
  const [toasts, setToasts] = useState<Toast[]>([])
  const [dragging, setDragging] = useState(false)
  const toastId = useRef(1)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const editorRef = useRef<HTMLDivElement | null>(null)
  const onThreadChangeRef = useRef(onThreadChange)
  onThreadChangeRef.current = onThreadChange

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
      onThreadChangeRef.current?.(page.thread)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load messages')
    } finally {
      setLoading(false)
    }
  }, [thread.id])

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
  const toLine = lastInbound?.from.address || thread.participants?.find((item) => item !== fromAddress) || thread.participants?.[0] || ''
  const ccLine = (lastInbound?.cc || []).filter(Boolean)
  const toList = toLine ? [toLine] : []
  const mailboxFrom = fromAddress || thread.participants?.find((item) => item.includes('@')) || ''
  const filledTemplate = templateId ? fillTemplate(templates.find((item) => item.id === templateId)?.body || '', vars) : ''

  function resetComposer() {
    setBody('')
    setBodyHtml('')
    setFiles([])
    setFileErrors([])
    setSuggestions([])
    setSuggestError(null)
    setSendError(null)
    setTemplateId('')
    if (editorRef.current) editorRef.current.innerHTML = ''
  }

  function takeFiles(incoming: File[]) {
    const checked = validateAttachments(incoming, files)
    setFileErrors(checked.rejected.map((item) => item.reason))
    setFiles(checked.accepted)
  }

  function syncEditor() {
    const el = editorRef.current
    if (!el) return
    setBodyHtml(el.innerHTML)
    setBody(htmlToPlain(el.innerHTML))
  }

  function applyFormat(command: string, value?: string) {
    editorRef.current?.focus()
    document.execCommand(command, false, value)
    syncEditor()
  }

  function insertTemplateText(text: string) {
    if (plainMode) {
      const el = composerRef.current
      const start = el?.selectionStart ?? body.length
      const end = el?.selectionEnd ?? body.length
      const next = insertAtCaret(body, text, start, end)
      setBody(next.text)
      setBodyHtml(plainToHtml(next.text))
      requestAnimationFrame(() => {
        if (!el) return
        el.focus()
        el.setSelectionRange(next.caret, next.caret)
      })
      return
    }
    editorRef.current?.focus()
    document.execCommand('insertHTML', false, plainToHtml(text))
    syncEditor()
  }

  async function sendNow() {
    if (!body.trim() || leftovers.length) return
    setSending(true)
    setSendError(null)
    const pendingId = `pending-${Date.now()}`
    const pending: EmailMessage = {
      id: pendingId,
      threadId: thread.id,
      from: { address: mailboxFrom, name: 'You' },
      to: toList,
      cc: ccLine,
      subject,
      bodyText: body,
      bodyHtml: plainMode ? undefined : bodyHtml || plainToHtml(body),
      receivedAt: new Date().toISOString(),
      isIncoming: false,
      isRead: true,
      deliveryStatus: 'pending',
      hasAttachments: files.length > 0,
      attachments: files.map((file, index) => ({
        id: `local-${index}`,
        fileName: file.name,
        size: file.size,
        contentType: file.type || 'application/octet-stream',
        status: 'pending',
      })),
    }
    setMessages((prev) => [...prev, pending])
    try {
      const sent = await emailApi.reply(thread.id, {
        bodyText: body,
        bodyHtml: plainMode ? undefined : bodyHtml || plainToHtml(body),
        templateId: templateId || undefined,
        variables: vars,
        idempotencyKey: `${thread.id}-${Date.now()}`,
        attachments: files.map((file) => ({
          fileName: file.name,
          contentType: file.type || 'application/octet-stream',
          size: file.size,
        })),
      })
      setMessages((prev) => prev.map((item) => (item.id === pendingId ? sent : item)))
      resetComposer()
      setComposing(false)
      toast('Sent')
    } catch (err) {
      setMessages((prev) =>
        prev.map((item) => (item.id === pendingId ? { ...item, deliveryStatus: 'error' } : item)),
      )
      setSendError(err instanceof Error ? err.message : 'Could not send')
    } finally {
      setSending(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (needsSendConfirm({ to: toList, cc: ccLine, subject })) {
      setConfirmOpen(true)
      return
    }
    void sendNow()
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
    setMenuOpen(false)
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

  useEffect(() => {
    if (!linkOpen) return
    const handle = window.setTimeout(() => {
      void jobsApi
        .list({
          sources: ['greenhouse', 'lever'],
          q: jobQuery,
          location: '',
          status: 'all',
          limit: 50,
          cursor: null,
        })
        .then((page) => setJobs(page.items))
        .catch(() => setJobs([]))
    }, 200)
    return () => window.clearTimeout(handle)
  }, [jobQuery, linkOpen])

  const filteredJobs = jobs.filter((job) => {
    const blob = `${job.title} ${job.company}`.toLowerCase()
    return !jobQuery || blob.includes(jobQuery.toLowerCase())
  })

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragging(false)
    takeFiles(Array.from(event.dataTransfer.files || []))
  }

  return (
    <div className={`email-pane ${compact ? 'email-pane-compact' : ''}`}>
      <div className="email-pane-head">
        <div>
          <h2>{thread.subject}</h2>
          <p className="muted">
            From: {mailboxFrom || 'your mailbox'}
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
          <div className="overflow-menu">
            <button
              type="button"
              className="secondary"
              aria-label="Thread actions"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              More
            </button>
            {menuOpen && (
              <ul className="overflow-menu-list" role="menu">
                {thread.linked && (
                  <li role="none">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false)
                        setUnlinkOpen(true)
                      }}
                    >
                      Unlink from job
                    </button>
                  </li>
                )}
                {!thread.linked && (
                  <li role="none">
                    <button type="button" role="menuitem" onClick={() => void openLink()}>
                      Link to job
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>
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
            {item.bodyHtml ? (
              <div className="message-body message-html" dangerouslySetInnerHTML={{ __html: sanitizeMailHtml(item.bodyHtml) }} />
            ) : (
              <p className="message-body">{item.bodyText}</p>
            )}
            {item.deliveryStatus === 'pending' && (
              <p className="muted" role="status">
                Sending…
              </p>
            )}
            {item.deliveryStatus === 'error' && (
              <p className="inline-error" role="status">
                Could not send this reply.
              </p>
            )}
            {item.attachments.length > 0 && (
              <ul className="attach-list">
                {item.attachments.map((file) => {
                  const kind = attachmentKind(file.contentType, file.fileName)
                  return (
                    <li key={file.id}>
                      <span className="attach-kind" aria-hidden="true">
                        {kind === 'pdf' ? 'PDF' : kind === 'image' ? 'IMG' : 'FILE'}
                      </span>{' '}
                      {file.fileName} · {attachmentKindLabel(kind)} · {fileSize(file.size)}
                      {file.status === 'skipped_oversize' ? ' (too large)' : ''}
                      {file.status === 'stored' && file.downloadUrl ? (
                        <>
                          {' · '}
                          <a
                            href={file.downloadUrl}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(event) => {
                              if (!attachmentNeedsAuthFetch(file.downloadUrl)) return
                              event.preventDefault()
                              void (async () => {
                                try {
                                  const { request } = await import('../api/live')
                                  const resp = await request(file.downloadUrl!)
                                  if (!resp.ok) throw new Error('Could not open attachment')
                                  const blob = await resp.blob()
                                  const objectUrl = URL.createObjectURL(blob)
                                  window.open(objectUrl, '_blank', 'noopener,noreferrer')
                                } catch (err) {
                                  toast(err instanceof Error ? err.message : 'Could not open attachment', 'error')
                                }
                              })()
                            }}
                          >
                            {previewable(file.contentType, file.fileName) ? 'Preview' : 'Download'}
                          </a>
                        </>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            )}
          </li>
        ))}
      </ol>
      {!composing && (
        <div className="actions">
          <button type="button" className="primary" onClick={() => setComposing(true)} aria-label="Reply to this thread">
            Reply
          </button>
        </div>
      )}
      {composing && (
        <form
          className={`composer ${dragging ? 'is-dragging' : ''}`}
          onSubmit={onSubmit}
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <p className="muted">
            From: {mailboxFrom || 'your mailbox'} (read-only)
          </p>
          <p className="muted">To: {toLine || '—'}</p>
          {ccLine.length > 0 && <p className="muted">CC: {ccLine.join(', ')}</p>}
          <p className="muted">Subject: {subject || '(empty)'}</p>
          <div className="composer-tools">
            <label>
              Template
              <select
                aria-label="Reply template"
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
              >
                <option value="">Choose a template</option>
                {templates.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="secondary"
              disabled={!templateId}
              onClick={() => {
                if (!filledTemplate) return
                insertTemplateText(filledTemplate)
              }}
            >
              Insert at caret
            </button>
            <button type="button" className="secondary" onClick={() => void generate()}>
              Generate reply
            </button>
            <button
              type="button"
              className="secondary"
              aria-pressed={plainMode}
              onClick={() => {
                if (plainMode) {
                  setPlainMode(false)
                  requestAnimationFrame(() => {
                    if (editorRef.current) editorRef.current.innerHTML = bodyHtml || plainToHtml(body)
                  })
                } else {
                  syncEditor()
                  setPlainMode(true)
                }
              }}
            >
              {plainMode ? 'Rich text' : 'Plain text'}
            </button>
          </div>
          {filledTemplate && (
            <p className="template-preview" aria-live="polite">
              Preview: {filledTemplate}
              {leftoverVars(filledTemplate).length > 0 && (
                <span className="warn-text"> Unresolved: {leftoverVars(filledTemplate).join(', ')}</span>
              )}
            </p>
          )}
          {!plainMode && (
            <div className="rich-toolbar" role="toolbar" aria-label="Formatting">
              <button type="button" aria-label="Bold" onClick={() => applyFormat('bold')}>
                B
              </button>
              <button type="button" aria-label="Italic" onClick={() => applyFormat('italic')}>
                I
              </button>
              <button type="button" aria-label="Underline" onClick={() => applyFormat('underline')}>
                U
              </button>
              <button type="button" aria-label="Bulleted list" onClick={() => applyFormat('insertUnorderedList')}>
                List
              </button>
              <button
                type="button"
                aria-label="Insert link"
                onClick={() => {
                  const href = window.prompt('Link URL')
                  if (href) applyFormat('createLink', href)
                }}
              >
                Link
              </button>
            </div>
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
                      setBodyHtml(plainToHtml(item.text))
                      if (editorRef.current && !plainMode) editorRef.current.innerHTML = plainToHtml(item.text)
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
          {plainMode ? (
            <textarea
              id={`reply-${thread.id}`}
              ref={composerRef}
              value={body}
              onChange={(event) => {
                setBody(event.target.value)
                setBodyHtml(plainToHtml(event.target.value))
              }}
              rows={compact ? 5 : 8}
              placeholder="Write a reply…"
              required
            />
          ) : (
            <div
              id={`reply-${thread.id}`}
              ref={editorRef}
              className="composer-editor"
              contentEditable
              role="textbox"
              aria-multiline="true"
              aria-label="Reply"
              data-placeholder="Write a reply…"
              onInput={syncEditor}
            />
          )}
          {leftovers.length > 0 && (
            <p className="warn-text">
              Fill template fields:{' '}
              {leftovers.map((item) => (
                <mark key={item}>{`{${item}}`}</mark>
              ))}
            </p>
          )}
          {fileErrors.map((item) => (
            <p key={item} className="inline-error">
              {item}
            </p>
          ))}
          <div className="composer-files">
            <label className="secondary file-btn">
              Attach
              <input
                type="file"
                multiple
                className="sr-only"
                onChange={(event) => {
                  takeFiles(Array.from(event.target.files || []))
                  event.target.value = ''
                }}
              />
            </label>
            <span className="muted">or drop files here · PNG, JPG, PDF preview; max 20 files / 25 MB</span>
            {files.map((file) => (
              <button
                key={file.name}
                type="button"
                className="chip"
                aria-label={`Remove ${file.name}`}
                onClick={() => setFiles((prev) => prev.filter((item) => item !== file))}
              >
                {file.name} · {fileSize(file.size)} ×
              </button>
            ))}
          </div>
          {sendError && (
            <p className="inline-error">
              {sendError}{' '}
              <button type="button" className="link-btn" onClick={() => void sendNow()}>
                Retry
              </button>
            </p>
          )}
          <div className="actions">
            <button type="submit" className="primary" disabled={sending || !body.trim() || leftovers.length > 0}>
              {sending ? 'Sending…' : 'Send'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                resetComposer()
                setComposing(false)
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((item) => item.id !== id))} />
      {confirmOpen && (
        <Modal title="Send this reply?" onClose={() => setConfirmOpen(false)}>
          <p>
            {ccLine.length + toList.length > 1
              ? `This reply goes to ${[...toList, ...ccLine].filter(Boolean).join(', ')}.`
              : 'This reply has an empty subject.'}
          </p>
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={() => {
                setConfirmOpen(false)
                void sendNow()
              }}
            >
              Send
            </button>
            <button type="button" className="secondary" onClick={() => setConfirmOpen(false)}>
              Cancel
            </button>
          </div>
        </Modal>
      )}
      {linkOpen && (
        <Modal title="Link to job" onClose={() => setLinkOpen(false)}>
          <label>
            Search jobs
            <input
              value={jobQuery}
              onChange={(event) => setJobQuery(event.target.value)}
              placeholder="Title or company"
              aria-label="Search jobs by title or company"
            />
          </label>
          <ul className="job-pick">
            {filteredJobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const updated = await emailApi.link(thread.id, job.id)
                      onThreadChangeRef.current?.(updated)
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
                onThreadChangeRef.current?.(updated)
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
