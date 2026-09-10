import { emailHref, jobHref, reviewHref } from '../lib/routes'

export function JobCrossLinks({
  jobId,
  matchId,
  current,
}: {
  jobId: string
  matchId?: string | null
  current: 'jobs' | 'review' | 'email' | 'apply'
}) {
  if (!jobId) return null
  return (
    <nav className="job-cross-links" aria-label="Related screens">
      {current !== 'jobs' && (
        <a className="primary-link" href={jobHref(jobId)}>
          Job
        </a>
      )}
      {current !== 'review' && (
        <a className="primary-link" href={reviewHref({ matchId, jobId })}>
          Review
        </a>
      )}
      {current !== 'email' && (
        <a className="primary-link" href={emailHref({ jobId })}>
          Email
        </a>
      )}
    </nav>
  )
}
