# AJAS HTTP API

REST Client (VS Code) / IntelliJ HTTP samples for the live AJAS Functions
endpoints. Start the backend with `cd backend && func start`, then send
requests against `http://localhost:7071`.

Local auth (`AUTH_MODE=dev`) accepts `Authorization: Bearer <user-id>`.
The examples use `local-user`, which matches the frontend default.

| Collection | Coverage |
| --- | --- |
| [review.http](review.http) | Match queue, saved-jobs sort, approve/reject, decision list/history |
| [settings.http](settings.http) | Threshold, source toggles, Microsoft 365 connect/callback/disconnect |

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
  "features": ["health", "review", "auto-apply", "settings"]
}
```

Successful Review/Settings calls are logged as `ajas.request` with
`feature`, `route`, `method`, `status`, and `user_id`. Failures add `error`
and an `ajas.error` traceback.
