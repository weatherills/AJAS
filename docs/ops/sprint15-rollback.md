# Sprint 15 rollback

1. `git revert` the wrap-up commit or the last known-good SHA.
2. Keep `FLAG_*` adapter flags false.
3. Redeploy Azure Functions and the frontend.
4. Confirm `GET /api/health` reports `version: sprint14` only if you fully roll back the health bump; otherwise expect `sprint15`.
