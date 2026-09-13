# DPIA notes and robots/site-policy

AJAS ingests **public** Greenhouse and Lever job boards. Optional boards
(Indeed, LinkedIn, Glassdoor, Wellfound, Workday, ZipRecruiter) are
**fixture-only**. Live HTML scraping of those sites is out of the Job Source
PRD.

## Data

- Job postings are public listings. Descriptions are stored after HTML strip
  and email redaction.
- Resumes and mail are user-owned. Logs use `redact_pii` (email, phone, SSN,
  payment-card patterns).
- GDPR export/purge lives in Settings (`ajas.gdpr.v1`).

## Robots and consent

| Flag | Default | Effect |
| --- | --- | --- |
| `FLAG_RESPECT_ROBOTS` | true | `can_fetch` fail-closed on robots.txt |
| `FLAG_SITE_POLICY_CONSENT` | false | Required before any optional-board HTTP |

Operators must not enable optional-board flags against live third-party HTML.
Fixture hosts are `fixtures.ajas.local` / localhost.

## Lawful basis (operator checklist)

- Job data: legitimate interest in matching public ads to a consenting user.
- Resume/mail: contract / consent of the account owner.
- Auto-apply: explicit per-job consent; CAPTCHA/SSO → `needs_manual` (never bypass).
