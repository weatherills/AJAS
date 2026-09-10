# AJAS HTTP API

REST Client (VS Code) / IntelliJ HTTP samples for the live AJAS Functions
endpoints. Start the backend with `cd backend && func start`, then send
requests against `http://localhost:7071`.

Local auth (`AUTH_MODE=dev`) accepts `Authorization: Bearer <user-id>`.
The examples use `local-user`, which matches the frontend default.

| Collection | Coverage |
| --- | --- |
| [review.http](review.http) | Match queue, saved-jobs sort, approve/reject, decision list/history |
| [settings.http](settings.http) | Threshold, Auto-Apply flag, audit trail, source toggles, Microsoft 365 connect |
| [resume.http](resume.http) | Upload, list, detail, preview URL, patch, retry-parse, run active resume |
| [jobs.http](jobs.http) | Job feed, source status, on-demand Greenhouse/Lever crawl |
| [matching.http](matching.http) | Compute/rank scores, warmup, A/B variant, SLO snapshot, list persisted results |
| [email.http](email.http) | Graph webhook, mailbox status, threads, reply, suggestions, link |
| [learning.http](learning.http) | Decision log, params, admin tune, metrics |

Health (no auth):

```
GET http://localhost:7071/api/health
```

Expected 200:

```json
{
  "status": "ok",
  "service": "ajas-backend",
  "authMode": "dev",
  "storage": "memory",
  "features": ["health", "review", "auto-apply", "settings", "resume", "jobs", "matching", "email", "learning"]
}
```

Successful Review/Settings calls are logged as `ajas.request` with
`feature`, `route`, `method`, `status`, and `user_id`. Failures add `error`
and an `ajas.error` traceback.
