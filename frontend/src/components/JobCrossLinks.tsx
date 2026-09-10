import { applyHref, emailHref, jobHref, resumeHref, reviewHref } from '../lib/routes'

export function JobCrossLinks({
  jobId,
  matchId,
  resumeId,
  current,
}: {
  jobId: string
  matchId?: string | null
  resumeId?: string | null
  current: 'jobs' | 'review' | 'email' | 'apply' | 'resume'
}) {
  if (!jobId && !resumeId) return null
  return (
    <nav className="job-cross-links" aria-label="Related screens">
      {current !== 'jobs' && jobId && (
        <a className="primary-link" href={jobHref(jobId)}>
          Job
        </a>
      )}
      {current !== 'review' && jobId && (
        <a className="primary-link" href={reviewHref({ matchId, jobId, resumeId })}>
          Review
        </a>
      )}
      {current !== 'email' && jobId && (
        <a className="primary-link" href={emailHref({ jobId })}>
          Email
        </a>
      )}
      {current !== 'apply' && jobId && (
        <a className="primary-link" href={applyHref(null, jobId)}>
          Apply
        </a>
      )}
      {current !== 'resume' && resumeId && (
        <a className="primary-link" href={resumeHref(resumeId)}>
          Resume
        </a>
      )}
    </nav>
  )
}
